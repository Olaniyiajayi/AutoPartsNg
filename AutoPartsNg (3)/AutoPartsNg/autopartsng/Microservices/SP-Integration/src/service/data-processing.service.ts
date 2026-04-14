import axios from 'axios';
import { BatchWriteItemCommand, DynamoDBClient, ScanCommand } from '@aws-sdk/client-dynamodb';
import {
  DDI_CONTACTNAME,
  DDI_PASSPHRASE,
  DDI_PASSWORD,
  DDI_USERNAME,
  MANAGE_INVENTORY_TABLE,
  MANAGE_SKU_TABLE,
  SP_MARKETPLACE_ID,
} from '../config/env.config';
import { FEED_STATUS, SP_API_URL } from '../constants/sp.constants';
import { IProcessedStockItem } from '../interface/data-processing.interface';
import { DDI_API_URL } from '../constants/ddi.constants';

const dynamoDB = new DynamoDBClient();

export const getAmazonSkuList = async (
  accessToken: string,
  nextToken: string | null = null,
  collectedSKUs: { stockNum: string }[] = [],
): Promise<
  {
    stockNum: string;
  }[]
> => {
  console.log(':::::::::: GETTING AMAZON SKU ::::::::::');
  try {
    const params: Record<string, any> = {
      marketplaceIds: SP_MARKETPLACE_ID,
      pageSize: 20,
    };

    if (nextToken) {
      params.pageToken = nextToken;
    }

    const response = await axios.get(SP_API_URL.ITEM_LISTING, {
      params,
      headers: {
        'x-amz-access-token': accessToken, // Replace with your token
        'Content-Type': 'application/json',
      },
    });

    const data = response.data;
    if (data.items && Array.isArray(data.items)) {
      collectedSKUs.push(
        ...data.items.map((item: { sku: string }) => {
          return {
            stockNum: item.sku,
          };
        }),
      );
    }

    // If there is a nextToken, recursively fetch the next page
    if (data.pagination?.nextToken) {
      return getAmazonSkuList(accessToken, data.pagination.nextToken, collectedSKUs);
    }

    // No more pages, return the collected SKUs
    return collectedSKUs;
  } catch (error: any) {
    console.error('Error fetching data:', error.response.data);
    return collectedSKUs; // Return what has been collected so far
  }
};

export const fetchDatabaseSkus = async () => {
  let items: any[] = [];
  let ExclusiveStartKey = undefined;

  do {
    const params = {
      TableName: MANAGE_SKU_TABLE,
      ExclusiveStartKey, // For pagination
    };

    const command = new ScanCommand(params);
    const response: any = await dynamoDB.send(command);

    if (response.Items) {
      items = [...items, ...response.Items];
    }

    ExclusiveStartKey = response.LastEvaluatedKey; // Continue pagination
  } while (ExclusiveStartKey);

  console.log('Total Items Fetched::::', items.length);
  return items;
};

export const validateDDIUser = async () => {
  const validUserPayload = {
    DDIRequest: {
      schema: 'ecommprovalidateuser',
      userName: DDI_USERNAME,
      password: DDI_PASSWORD,
      passPhrase: DDI_PASSPHRASE,
      contactName: DDI_CONTACTNAME,
    },
  };

  return await axios.post(DDI_API_URL.VALIDATE_DDI_USER, validUserPayload);
};

export const getDDIStocks = async (
  token: string,
  branch: string,
  accountNumber: string,
  userId: string,
  amazonSkuList: { stockNum: string }[],
) => {
  const getStockPayload = {
    DDIRequest: {
      schema: 'EcommProPriceStock',
      userName: DDI_USERNAME,
      password: DDI_PASSWORD,
      passPhrase: DDI_PASSPHRASE,
      token,
      branch,
      accountNumber,
      userId,
      allWarehouse: 'Y',
      priceOnly: 'N',
      stockOnly: 'Y',
      itemList: amazonSkuList,
    },
  };

  const getStocks = await axios.post(DDI_API_URL.GET_STOCKS, getStockPayload);
  return getStocks?.data?.DDIResponse?.itemData;
};

export const chunkArray = (array: any, size: number) => {
  return Array.from({ length: Math.ceil(array.length / size) }, (_, i) => array.slice(i * size, i * size + size));
};

export const prepareBatchItems = (items: IProcessedStockItem[], isUpdate = false) => {
  const timestamp = new Date().toISOString();

  return chunkArray(items, 25).map((batch) => ({
    RequestItems: {
      [MANAGE_INVENTORY_TABLE]: batch.map((item: any) => ({
        PutRequest: {
          Item: {
            sku: { S: item.sku },
            quantity: { S: item.quantity.toString() },
            feed_status: { S: FEED_STATUS.IN_QUEUE },
            updatedAt: { S: timestamp },
            createdAt: { S: isUpdate ? item.createdAt : timestamp },
          },
        },
      })),
    },
  }));
};

export const performBatchWrite = async (batches: any) => {
  for (const batch of batches) {
    try {
      const batchWriteCommand = new BatchWriteItemCommand(batch);
      await dynamoDB.send(batchWriteCommand);
    } catch (error) {
      console.error('Batch write failed:', error);
    }
  }
};
