import { DynamoDBClient, UpdateItemCommand } from '@aws-sdk/client-dynamodb';
import { SellingPartner } from 'amazon-sp-api';
import { create } from 'xmlbuilder2';
import { IFeedRawData } from '../interface/inventory-feed.interface';
import {
  MANAGE_INVENTORY_TABLE,
  SP_APP_CLIENT_ID,
  SP_APP_CLIENT_SECRET,
  SP_MARKETPLACE_ID,
  SP_REFRESH_TOKEN,
  SP_REGION,
  SP_SELLER_ID,
} from '../config/env.config';

const sellingPartner = new SellingPartner({
  region: SP_REGION as 'eu' | 'na' | 'fe', // 'na' for North America, 'eu' for Europe, 'fe' for Far East
  refresh_token: SP_REFRESH_TOKEN,
  credentials: {
    SELLING_PARTNER_APP_CLIENT_ID: SP_APP_CLIENT_ID,
    SELLING_PARTNER_APP_CLIENT_SECRET: SP_APP_CLIENT_SECRET,
  },
});

const dynamoDB = new DynamoDBClient();

// Generate XML Feed
export const generateFeedXML = (feedRawData: IFeedRawData[]): string => {
  const root = create({ version: '1.0', encoding: 'UTF-8' })
    .ele('AmazonEnvelope', {
      'xmlns:xsi': 'http://www.w3.org/2001/XMLSchema-instance',
      'xsi:noNamespaceSchemaLocation': 'amzn-envelope.xsd',
    })
    .ele('Header')
    .ele('DocumentVersion')
    .txt('1.01')
    .up()
    .ele('MerchantIdentifier')
    .txt(SP_SELLER_ID)
    .up()
    .up() // Close Header
    .ele('MessageType')
    .txt('Inventory')
    .up();

  feedRawData.forEach((item, index) => {
    root
      .ele('Message')
      .ele('MessageID')
      .txt((index + 1).toString())
      .up()
      .ele('OperationType')
      .txt('Update')
      .up()
      .ele('Inventory')
      .ele('SKU')
      .txt(item.sku)
      .up()
      .ele('Quantity')
      .txt(item.quantity)
      .up()
      .up() // Close Inventory
      .up(); // Close Message
  });

  return root.end({ prettyPrint: true });
};

// Generate JSON Feed
export const generateFeedJSON = (feedRawData: IFeedRawData[]) => {
  return {
    header: {
      sellerId: SP_SELLER_ID,
      version: '2.0',
      issueLocale: 'en_US',
    },
    messages: feedRawData.map((item, index) => ({
      messageId: index + 1,
      sku: item.sku,
      operationType: 'PATCH',
      productType: 'PRODUCT',
      patches: [
        {
          op: 'replace',
          path: '/attributes/fulfillment_availability',
          value: [
            {
              fulfillment_channel_code: 'DEFAULT',
              quantity: item.quantity,
            },
          ],
        },
      ],
    })),
  };
};

// Generate Feed document
export const generateFeedDocument = async () => {
  return await sellingPartner.callAPI({
    operation: 'createFeedDocument',
    endpoint: 'feeds',
    body: {
      contentType: 'text/xml; charset=utf-8',
    },
  });
};

// Upload XML Feed to update inventory to amazon
export const uploadFeed = async (feedDocument: { url: string }, feedContent: string) => {
  await sellingPartner.upload(feedDocument, {
    content: feedContent,
    contentType: 'text/xml; charset=utf-8',
  });
};

// create feed
export const createFeed = async (feedDocument: { feedDocumentId: string }) => {
  return await sellingPartner.callAPI({
    operation: 'createFeed',
    endpoint: 'feeds',
    body: {
      marketplaceIds: [SP_MARKETPLACE_ID],
      feedType: 'JSON_LISTINGS_FEED',
      inputFeedDocumentId: feedDocument.feedDocumentId,
    },
  });
};

// Get feed info
export const getFeed = async (feedId: string) => {
  return await sellingPartner.callAPI({
    operation: 'getFeed',
    endpoint: 'feeds',
    path: {
      feedId,
    },
  });
};

// Add feed id into dynamoDB database
export const addFeedIdInDB = async (data: any, feedInfo: any) => {
  for (const item of data) {
    const updateParams = {
      TableName: MANAGE_INVENTORY_TABLE,
      Key: { sku: { S: item.sku } },
      UpdateExpression: 'SET feedId = :feedId',
      ExpressionAttributeValues: { ':feedId': { S: feedInfo.feedId } },
    };

    await dynamoDB.send(new UpdateItemCommand(updateParams));
  }
};
