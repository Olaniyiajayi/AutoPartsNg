import { DynamoDBClient, BatchGetItemCommand } from '@aws-sdk/client-dynamodb';
import { SQSClient, SendMessageCommand } from '@aws-sdk/client-sqs';
import { IS_VALIDATE } from '../constants/ddi.constants';
import { MANAGE_INVENTORY_TABLE, PROCESSED_DATA_SQS_URL, SP_REFRESH_TOKEN } from '../config/env.config';
import { IItemToUpdate } from '../interface/data-processing.interface';
import {
  getDDIStocks,
  performBatchWrite,
  prepareBatchItems,
  validateDDIUser,
  chunkArray,
  fetchDatabaseSkus,
  getAmazonSkuList,
} from '../service/data-processing.service';
import { errorResponse, successResponse } from '../helpers/response.helper';
import { ERROR_MESSAGE, SUCCESS_MESSAGE } from '../constants/messages.contants';
import { getLwaToken } from '../service/subscription-notification.service';
import { LWA_GRANT_TYPES } from '../constants/sp.constants';

/**
 *
 * Event doc: https://docs.aws.amazon.com/apigateway/latest/developerguide/set-up-lambda-proxy-integrations.html#api-gateway-simple-proxy-for-lambda-input-format
 * @param {Object} event - API Gateway Lambda Proxy Input Format
 *
 * Return doc: https://docs.aws.amazon.com/apigateway/latest/developerguide/set-up-lambda-proxy-integrations.html
 * @returns {Object} object - API Gateway Lambda Proxy Output Format
 *
 */

const client = new DynamoDBClient();
const sqsClient = new SQSClient();

export const lambdaHandler = async () => {
  try {
    // Get the access token
    const accessToken = await getLwaToken(LWA_GRANT_TYPES.REFRESH_TOKEN, { refresh_token: SP_REFRESH_TOKEN });

    // Get the list of skus available at amazon
    const amazonSkuList = await getAmazonSkuList(accessToken.data);
    console.log('🚀 ~ lambdaHandler ~ amazonSkuList:', amazonSkuList.length);

    // Get all the sku from database
    const databaseSkus = await fetchDatabaseSkus();
    console.log('🚀 ~ lambdaHandler ~ databaseSkus:::', databaseSkus.length);

    const prepareDDISku: { stockNum: string }[] = [];

    // Add databased SKU's
    databaseSkus.map((item) => {
      prepareDDISku.push({ stockNum: item.ddiSku.S });
    });

    // Add amazon SKU's
    amazonSkuList.map((amazonItem) => {
      const exists = prepareDDISku.some((item) => item.stockNum === amazonItem.stockNum);
      if (!exists) prepareDDISku.push({ stockNum: amazonItem.stockNum });
    });
    console.log('🚀 ~ prepareDDISku ~ prepareDDISku::::', prepareDDISku.length);

    // Validate DDI User
    const isValidUser = await validateDDIUser();
    if (isValidUser?.data?.DDIResponse?.isValid !== IS_VALIDATE.YES)
      throw new Error(ERROR_MESSAGE.DDI_USER_VALIDATION_FAILED);

    const token = isValidUser.data.DDIResponse.token;
    const branch = isValidUser.data.DDIResponse.branch;
    const accountNumber = isValidUser.data.DDIResponse.user[0].accountNumber;
    const userId = isValidUser.data.DDIResponse.user[0].userId;

    // Get the DDI stock items
    const DDIStockItems = await getDDIStocks(token, branch, accountNumber, userId, prepareDDISku);
    if (!Array.isArray(DDIStockItems)) throw new Error(ERROR_MESSAGE.INVALID_STOCK_DATA);
    console.log('🚀 ~ lambdaHandler ~ DDIStockItems::::', DDIStockItems.length);

    const DDIStockMap = new Map(
      DDIStockItems.map((stockItem) => {
        // Less than 5 pcs inventory should update to Amazon as 0 stock (Only for branch 04)
        const stockNum = stockItem?.lineItem?.stockNum;

        let totalStock = 0;

        // Prepare a dynamic warehouse rule to handle managing custom inventory
        const warehouseRules: { [key: string]: (available: number) => number } = {
          // '04': (available: number) => (available > 5 ? available - 5 : 0), // Decrease 5 if more than 5 inventory
          // '05': (available: number) => available, // Take the all inventory
          '01': (available: number) => (available > 5 ? available - 5 : 0), // Same rule as branch 04
        };

        // Managing warehouse based inventory
        stockItem?.lineItem?.locations?.forEach(
          ({ warehouse, available }: { warehouse: string; available: string }) => {
            const avail = +available || 0;

            if (warehouseRules[warehouse]) {
              totalStock += warehouseRules[warehouse](avail);
            }
          },
        );

        // const availableStock = stockItem?.lineItem?.locations?.[0]?.available;
        // let ddiQuantity = availableStock;
        // if (ddiQuantity < 5) ddiQuantity = '0';

        return [stockNum, totalStock.toString()];
      }),
    );
    console.log('🚀 ~ lambdaHandler ~ DDIStockMap::::', DDIStockMap.size);

    const items: any[] = [];

    // Prepare a items to be update for database SKU's
    databaseSkus.map((sku) => {
      if (DDIStockMap.has(sku.ddiSku.S))
        items.push({ sku: sku.sellerSku.S, quantity: DDIStockMap.get(sku.ddiSku.S) ?? '0' });
    });

    // Prepare a items to be update for amazon SKU's
    amazonSkuList.map((sku) => {
      if (DDIStockMap.has(sku.stockNum)) {
        const exists = items.some((item) => item.sku === sku.stockNum);
        if (!exists) items.push({ sku: sku.stockNum, quantity: DDIStockMap.get(sku.stockNum) ?? '0' });
      }
    });
    console.log('🚀 ~ lambdaHandler ~ updatable items:::: ', items.length);

    const keys = items.map((item) => ({
      sku: { S: item.sku },
    }));

    // Check existing items in DynamoDB
    const existingItems: any[] = [];

    // Process BatchGetItem in chunks of 100
    const keyChunks = chunkArray(keys, 100);
    for (const chunk of keyChunks) {
      const batchGetParams = {
        RequestItems: { [MANAGE_INVENTORY_TABLE]: { Keys: chunk } },
      };

      const batchGetCommand = new BatchGetItemCommand(batchGetParams);
      const { Responses } = await client.send(batchGetCommand);

      if (Responses && Responses[MANAGE_INVENTORY_TABLE]) {
        existingItems.push(...Responses[MANAGE_INVENTORY_TABLE]);
      }
    }
    console.log('🚀 ~ lambdaHandler ~ existingItems::::', existingItems.length);

    // Prepare item to be insert
    const itemsToInsert = items.filter(
      (item) => !existingItems.find((existingItem) => existingItem.sku.S === item.sku),
    );

    // Prepare item to be update
    const itemsToUpdate: IItemToUpdate[] = [];
    items.map((item) => {
      const itemQty = item.quantity;
      // if (itemQty < 5) itemQty = '0';
      const existingItem = existingItems.find((e) => e.sku.S === item.sku && e.quantity.S !== itemQty);
      if (existingItem)
        return itemsToUpdate.push({ sku: item.sku, quantity: itemQty, createdAt: existingItem.createdAt.S! });
    });

    // Insert new items
    if (itemsToInsert.length) {
      const insertBatches = prepareBatchItems(itemsToInsert, false);
      await performBatchWrite(insertBatches);
    }
    console.log('🚀 ~ lambdaHandler ~ itemsToInsert::::', itemsToInsert.length);

    // Update items whose quantity should be updated
    if (itemsToUpdate.length) {
      const updateBatches = prepareBatchItems(itemsToUpdate, true);
      await performBatchWrite(updateBatches);
    }
    console.log('🚀 ~ lambdaHandler ~ itemsToUpdate:', itemsToUpdate.length);

    // Prepare a data to send in SQS
    const cleanUpdateItems = itemsToUpdate.map((item) => {
      delete item.createdAt;
      return item;
    });
    const updateFeedData = itemsToInsert.concat(cleanUpdateItems);
    console.log('🚀 ~ lambdaHandler ~ updateFeedData::::', updateFeedData.length);

    if (updateFeedData.length) {
      const params = {
        QueueUrl: PROCESSED_DATA_SQS_URL,
        MessageBody: JSON.stringify(updateFeedData),
        MessageGroupId: 'default-group',
      };
      console.log('🚀 ~ lambdaHandler ~ params:::::', params);

      try {
        const data = await sqsClient.send(new SendMessageCommand(params));
        console.log('Message sent to SQS::::', data.MessageId);
      } catch (error) {
        console.error('Error sending message to SQS::::', error);
      }
    }
    return successResponse(null, SUCCESS_MESSAGE.DATA_PROCESSED_SUCCESS);
  } catch (err: any) {
    console.log(err);
    return errorResponse(null, err.message || ERROR_MESSAGE.INTERNAL_SERVER_ERROR);
  }
};
