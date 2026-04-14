import { BatchWriteItemCommand, DynamoDBClient, GetItemCommand } from '@aws-sdk/client-dynamodb';
import {
  CREATE_ORDER_SQS_URL,
  MANAGE_ORDER_ITEM_TABLE,
  MANAGE_ORDER_TABLE,
  SP_REFRESH_TOKEN,
} from '../config/env.config';
import { ERROR_MESSAGE, SUCCESS_MESSAGE } from '../constants/messages.contants';
import { LWA_GRANT_TYPES, ORDER_STATUS } from '../constants/sp.constants';
import { errorResponse, successResponse } from '../helpers/response.helper';
import { fetchSyncedInventory, getOrderItemList, getOrderList } from '../service/create-order.service';
import { getLwaToken } from '../service/subscription-notification.service';
import { SendMessageCommand, SQSClient } from '@aws-sdk/client-sqs';
import { fetchDatabaseSkus } from '../service/data-processing.service';

const client = new DynamoDBClient();
const sqsClient = new SQSClient();

// Exclude FBA and V suffix SKU's
// const isFBASku = (sku: string): boolean => {
//   return /\s*-\s*(V|FBA)$/i.test(sku);
// };

export const lambdaHandler = async () => {
  try {
    // Get the access token
    const accessToken = await getLwaToken(LWA_GRANT_TYPES.REFRESH_TOKEN, { refresh_token: SP_REFRESH_TOKEN });

    // Get the order listing
    const orders = await getOrderList(accessToken.data);
    console.log('🚀 ~ lambdaHandler ~ orders:::::', orders);

    if (orders.length) {
      // Get all the sku from database
      const databaseSkus = await fetchDatabaseSkus();

      // Get all the synced inventory
      const syncedInventory = await fetchSyncedInventory();

      // Create order in Database
      for (const order of orders) {
        // Get the order item listing
        const orderItems = await getOrderItemList(accessToken.data, order.AmazonOrderId);
        console.log('🚀 ~ lambdaHandler ~ orderItems:::::', orderItems);

        // Collect the SKU's which needs to be created
        const orderItemData = [];
        for (const orderItem of orderItems) {
          // Create only if database SKU exists or synced inventory SKU
          const existingSku =
            databaseSkus.find((item) => item.sellerSku.S === orderItem.SellerSKU)?.ddiSku ||
            syncedInventory.find((item) => item.sku.S === orderItem.SellerSKU)?.sku;

          console.log('🚀 ~ lambdaHandler ~ existingSku:::::', existingSku);
          if (existingSku) {
            const itemPrice = Number(orderItem.ItemPrice?.Amount * 0.92) || 0; // Removing 8% from item amount
            const shippingPrice = Number(orderItem.ShippingPrice?.Amount) || 0;
            // const itemTax = Number(orderItem.ItemTax?.Amount) || 0;
            // const shippingTax = Number(orderItem.ShippingTax?.Amount) || 0;
            // const shippingDiscountTax = Number(orderItem.ShippingDiscountTax?.Amount) || 0;
            const promotionDiscount = Number(orderItem.PromotionDiscount?.Amount) || 0;
            // const promotionDiscountTax = Number(orderItem.PromotionDiscountTax?.Amount) || 0;

            let itemTotal: number | string = itemPrice + shippingPrice - promotionDiscount;

            itemTotal = itemTotal.toFixed(2).toString();

            const itemObj = {
              orderItemId: orderItem.OrderItemId,
              stockNum: existingSku.S, // Get the DDI SKU
              amazonSku: orderItem.SellerSKU,
              qty: orderItem.QuantityOrdered.toString(),
              ...(itemTotal && { price: itemTotal }),
              description: orderItem.Title,
            };
            orderItemData.push(itemObj);
          }
        }
        console.log('🚀 ~ lambdaHandler ~ orderItemData to be updated::::', orderItemData);
        if (!orderItemData.length) continue;

        // Check weather the order is created or not
        const params = {
          TableName: MANAGE_ORDER_TABLE,
          Key: { orderId: { S: order.AmazonOrderId } }, // Primary Key lookup
        };
        const response = await client.send(new GetItemCommand(params));
        console.log('🚀 ~ lambdaHandler ~ response::::', response.Item);

        // Create if order is not created before
        if (!response.Item) {
          const orderId = order.AmazonOrderId;
          const shippingAddress = order.ShippingAddress;

          // Prepare order item entries
          const orderItemEntries = orderItemData.map((item) => ({
            PutRequest: {
              Item: {
                orderId: { S: orderId },
                orderItemId: { S: item.orderItemId },
                sku: { S: item.stockNum },
                amazonSku: { S: item.amazonSku },
                quantity: { S: item.qty },
                price: { S: item.price },
                title: { S: item.description },
              },
            },
          }));

          // Create order entry
          const orderEntry: any = {
            PutRequest: {
              Item: {
                orderId: { S: orderId },
                purchaseDate: { S: order.PurchaseDate },
                lastUpdatedDate: { S: order.LastUpdateDate },
                creationStatus: { S: ORDER_STATUS.PENDING },
                createdAt: { S: new Date().toISOString() },
                shippingAddress: { S: JSON.stringify(shippingAddress) },
              },
            },
          };

          // Batch write (max 25 items per batch)
          const batchWriteParams = {
            RequestItems: {
              [MANAGE_ORDER_TABLE]: [orderEntry], // Orders table
              [MANAGE_ORDER_ITEM_TABLE]: orderItemEntries, // OrderItems table
            },
          };

          try {
            await client.send(new BatchWriteItemCommand(batchWriteParams));
            console.log(`Inserted order ${orderId} and its items successfully`);
          } catch (error) {
            console.error('Error inserting order and items:', error);
          }

          // Send orders to SQS
          const params = {
            QueueUrl: CREATE_ORDER_SQS_URL,
            MessageBody: JSON.stringify({ orderId: order.AmazonOrderId, shippingAddress: order.ShippingAddress }),
            MessageGroupId: 'OrdersGroup',
          };
          console.log('🚀 ~ lambdaHandler ~ params:::::', params);

          try {
            const data = await sqsClient.send(new SendMessageCommand(params));
            console.log('Message sent to SQS::::', data.MessageId);
          } catch (error) {
            console.error('Error sending message to SQS::::', error);
          }
        }
      }
    }

    return successResponse(null, SUCCESS_MESSAGE.ORDER_FETCHING_SUCCESS);
  } catch (err: any) {
    console.log(err);
    return errorResponse(null, err.message || ERROR_MESSAGE.INTERNAL_SERVER_ERROR);
  }
};
