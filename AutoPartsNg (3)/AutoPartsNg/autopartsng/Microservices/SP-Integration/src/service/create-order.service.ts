import axios from 'axios';
import {
  DDI_PASSPHRASE,
  DDI_PASSWORD,
  DDI_USERNAME,
  MANAGE_INVENTORY_TABLE,
  MANAGE_ORDER_ITEM_TABLE,
  MANAGE_ORDER_TABLE,
  SP_MARKETPLACE_ID,
} from '../config/env.config';
import { ORDER_STATUS, SP_API_URL } from '../constants/sp.constants';
import { DDI_API_URL } from '../constants/ddi.constants';
import { DynamoDBClient, QueryCommand, ScanCommand, UpdateItemCommand } from '@aws-sdk/client-dynamodb';
import { validateDDIUser } from './data-processing.service';

const dynamoDB = new DynamoDBClient();

// Get orders that update in last 1 hour
export const getOrderList = async (
  accessToken: string,
  nextToken: string | null = null,
  collectedOrders: any = [],
): Promise<any> => {
  try {
    // Get time 20 mins before in UTC
    const pastTime = new Date(new Date().getTime() - 60 * 20 * 1000);
    console.log('🚀 ~ pastTime::::', pastTime);

    const params: Record<string, any> = {
      MarketplaceIds: SP_MARKETPLACE_ID,
      LastUpdatedAfter: pastTime,
      OrderStatuses: 'Shipped',
    };

    if (nextToken) {
      params.NextToken = nextToken;
    }

    const response = await axios.get(SP_API_URL.ORDER_LISTING, {
      params,
      headers: {
        'x-amz-access-token': accessToken, // Replace with your token
        'Content-Type': 'application/json',
      },
    });

    const data = response.data;
    if (data.payload.Orders && Array.isArray(data.payload.Orders)) {
      collectedOrders.push(...data.payload.Orders);
    }

    // If there is a nextToken, recursively fetch the next page
    if (data.payload.NextToken) {
      return getOrderList(accessToken, data.payload.NextToken, collectedOrders);
    }

    // No more pages, return the collected SKUs
    return collectedOrders;
  } catch (error: any) {
    console.error('Error fetching data:', error.response.data);
    return collectedOrders; // Return what has been collected so far
  }
};

// Get order items
export const getOrderItemList = async (accessToken: string, orderId: string): Promise<any> => {
  try {
    const response = await axios.get(`https://sellingpartnerapi-na.amazon.com/orders/v0/orders/${orderId}/orderItems`, {
      headers: {
        'x-amz-access-token': accessToken,
        'Content-Type': 'application/json',
      },
    });

    return response.data.payload.OrderItems;
  } catch (error: any) {
    console.error('Error fetching data:', error.response.data);
    return false;
  }
};

// Create order in DDI
export const createDDIOrder = async (
  token: string,
  branch: string,
  accountNumber: string,
  userDetails: { userId: string; userName: string; firstName: string; lastName: string; email: string },
  orderId: string,
  orderItemData: any[],
  shippingAddress: { City: string; StateOrRegion: string; PostalCode: string; CountryCode: string },
) => {
  const createOrderPayload = {
    DDIRequest: {
      schema: 'EcommProSubmitOrder',
      userName: DDI_USERNAME,
      password: DDI_PASSWORD,
      passPhrase: DDI_PASSPHRASE,
      token,
      branch,
      accountNumber,
      user: userDetails,
      purchaseOrder: orderId,
      shipAddress: {
        shipCity: shippingAddress.City,
        shipState: shippingAddress.StateOrRegion,
        shipPostCode: shippingAddress.PostalCode,
        shipCountry: shippingAddress.CountryCode,
        validateOnly: 'N',
      },
      lineItems: {
        itemData: orderItemData,
      },
      shipMethod: 'dhl_V',
      orderType: 'ECOMM',
      orderTypeDescription: 'Web Order',
    },
  };

  const createdOrder = await axios.post(DDI_API_URL.CREATE_ORDER, createOrderPayload);
  return createdOrder?.data;
};

// Get all the synced inventory
export const fetchSyncedInventory = async () => {
  let items: any[] = [];
  let ExclusiveStartKey = undefined;

  do {
    const params = {
      TableName: MANAGE_INVENTORY_TABLE,
      ExclusiveStartKey, // For pagination
    };

    const command = new ScanCommand(params);
    const response: any = await dynamoDB.send(command);

    if (response.Items) {
      items = [...items, ...response.Items];
    }

    ExclusiveStartKey = response.LastEvaluatedKey; // Continue pagination
  } while (ExclusiveStartKey);

  console.log('Total Synced Inventory Fetched::::', items.length);
  return items;
};

// Handle order creation and update status
export const handleOrderCreation = async (order: {
  orderId: string;
  shippingAddress: { City: string; StateOrRegion: string; PostalCode: string; CountryCode: string };
}) => {
  // Get the order items
  const params = {
    TableName: MANAGE_ORDER_ITEM_TABLE,
    KeyConditionExpression: 'orderId = :orderId',
    ExpressionAttributeValues: {
      ':orderId': { S: order.orderId },
    },
  };

  const orderItems = await dynamoDB.send(new QueryCommand(params));
  console.log('🚀 ~ lambdaHandler ~ orderItems::::', orderItems.Items);

  // Prepare a order to be created in DDI
  if (orderItems.Items?.length) {
    const orderItemData = [];
    for (const orderItem of orderItems.Items) {
      const itemObj = {
        stockNum: orderItem.sku.S,
        qty: orderItem.quantity.S,
        // price: orderItem.price.S / orderItem.quantity.S, // price per unit
        description: orderItem.title.S,
      };
      orderItemData.push(itemObj);
    }
    console.log('🚀 ~ lambdaHandler ~ orderItemData to be updated::::', orderItemData);

    // Validate DDI User
    const isValidUser = await validateDDIUser();
    const token = isValidUser.data.DDIResponse.token;
    const branch = '01';
    const accountNumber = isValidUser.data.DDIResponse.user[0].accountNumber;
    const userId = isValidUser.data.DDIResponse.user[0].userId;
    const userName = isValidUser.data.DDIResponse.user[0].userName;
    const firstName = isValidUser.data.DDIResponse.user[0].firstName;
    const lastName = isValidUser.data.DDIResponse.user[0].lastName;
    const email = isValidUser.data.DDIResponse.user[0].email;

    const userDetails = {
      userId,
      userName,
      firstName,
      lastName,
      email,
    };

    // Create order in DDI
    const createdOrder = await createDDIOrder(
      token,
      branch,
      accountNumber,
      userDetails,
      order.orderId,
      orderItemData,
      order.shippingAddress,
    );
    console.log('🚀 ~ lambdaHandler ~ createdOrder::::', createdOrder.DDIResponse);

    // Update the creation status in database
    if (createdOrder?.DDIResponse) {
      const params = {
        TableName: MANAGE_ORDER_TABLE,
        Key: { orderId: { S: order.orderId } },
        UpdateExpression: 'SET creationStatus = :status',
        ExpressionAttributeValues: { ':status': { S: ORDER_STATUS.DONE } },
      };

      const command = new UpdateItemCommand(params);
      await dynamoDB.send(command);
    }
  }
};
