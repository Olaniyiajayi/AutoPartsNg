import { DynamoDBClient, ScanCommand, UpdateItemCommand } from '@aws-sdk/client-dynamodb';
import { MANAGE_INVENTORY_TABLE } from '../config/env.config';
import { FEED_STATUS } from '../constants/sp.constants';

const dynamoDB = new DynamoDBClient();

// Get IN QUEUE items to check the feed status
export const getInQueueItems = async () => {
  const params = {
    TableName: MANAGE_INVENTORY_TABLE,
    FilterExpression: 'feed_status = :status',
    ExpressionAttributeValues: { ':status': { S: FEED_STATUS.IN_QUEUE } },
  };

  const command = new ScanCommand(params);
  const { Items } = await dynamoDB.send(command);
  return Items || [];
};

// Function to update feed status in DynamoDB
export const updateFeedStatus = async (sku: string, newStatus: string) => {
  const params = {
    TableName: MANAGE_INVENTORY_TABLE,
    Key: { sku: { S: sku } },
    UpdateExpression: 'SET feed_status = :status, updatedAt = :updatedAt',
    ExpressionAttributeValues: { ':status': { S: newStatus }, ':updatedAt': { S: new Date().toISOString() } },
  };

  const command = new UpdateItemCommand(params);
  await dynamoDB.send(command);
};
