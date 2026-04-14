import { ERROR_MESSAGE, SUCCESS_MESSAGE } from '../constants/messages.contants';
import { errorResponse, successResponse } from '../helpers/response.helper';
import { handleOrderCreation } from '../service/create-order.service';

export const lambdaHandler = async (event: { Records: any }) => {
  console.log('🚀 ~ lambdaHandler ~ event:::::::', JSON.stringify(event));
  try {
    for (const record of event.Records) {
      const order = JSON.parse(record.body);
      console.log('QUEUE order::::::::', order);

      // Handle order creation and update status
      await handleOrderCreation(order);
    }

    return successResponse(null, SUCCESS_MESSAGE.ORDER_CREATE_SUCCESS);
  } catch (err: any) {
    console.log(err);
    return errorResponse(null, err.message || ERROR_MESSAGE.INTERNAL_SERVER_ERROR);
  }
};
