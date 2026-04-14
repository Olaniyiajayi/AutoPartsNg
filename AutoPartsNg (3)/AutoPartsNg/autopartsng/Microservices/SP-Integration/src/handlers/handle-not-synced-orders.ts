import { DynamoDBClient, ScanCommand } from '@aws-sdk/client-dynamodb';
import { ERROR_MESSAGE, SUCCESS_MESSAGE } from '../constants/messages.contants';
import { errorResponse, successResponse } from '../helpers/response.helper';
import { MANAGE_ORDER_TABLE } from '../config/env.config';
import { ORDER_STATUS } from '../constants/sp.constants';
import { handleOrderCreation } from '../service/create-order.service';

const client = new DynamoDBClient();

export const lambdaHandler = async () => {
  try {
    const params = {
      TableName: MANAGE_ORDER_TABLE,
      FilterExpression: '#creationStatus = :statusValue',
      ExpressionAttributeNames: {
        '#creationStatus': 'creationStatus',
      },
      ExpressionAttributeValues: {
        ':statusValue': { S: ORDER_STATUS.PENDING },
      },
    };

    const pendingOrders: any = await client.send(new ScanCommand(params));
    console.log('🚀 ~ lambdaHandler ~ pendingOrders:::::::', pendingOrders.Items);

    if (pendingOrders?.Items?.length) {
      for (let order of pendingOrders?.Items) {
        // Handle order creation and update status in database
        order = {
          orderId: order?.orderId?.S,
          shippingAddress: JSON.parse(order?.shippingAddress?.S),
        };
        await handleOrderCreation(order);
      }
    }

    return successResponse(null, SUCCESS_MESSAGE.ORDER_RESYNC_SUCCESS);
  } catch (err: any) {
    console.log(err);
    return errorResponse(null, err.message || ERROR_MESSAGE.INTERNAL_SERVER_ERROR);
  }
};
