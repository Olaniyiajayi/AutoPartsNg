import { SP_REFRESH_TOKEN } from '../config/env.config';
import { LWA_GRANT_TYPES, NOTIFICATION_DESTINATION } from '../constants/sp.constants';
import { errorResponse, successResponse } from '../helpers/response.helper';
import { ERROR_MESSAGE, SUCCESS_MESSAGE } from '../constants/messages.contants';
import {
  createDestination,
  createSubscription,
  getDestination,
  getLwaToken,
  getSubscription,
} from '../service/subscription-notification.service';

export const lambdaHandler = async () => {
  try {
    // Get SP-API Access Token & Grantless Access Token
    const [accessTokenResponse, grantlessTokenResponse] = await Promise.all([
      getLwaToken(LWA_GRANT_TYPES.REFRESH_TOKEN, { refresh_token: SP_REFRESH_TOKEN }),
      getLwaToken(LWA_GRANT_TYPES.CLIENT_CREDENTIALS, { scope: 'sellingpartnerapi::notifications' }),
    ]);

    const grantlessAccessToken = grantlessTokenResponse.data;
    const accessToken = accessTokenResponse.data;

    // Get Destination for SQS
    const getDestinationRes: any = await getDestination(grantlessAccessToken);
    const getDestinationData = getDestinationRes?.data;
    let getDestinationStatusCode = getDestinationRes?.status;
    console.log(
      '🚀 ~ lambdaHandler ~ getDestinationStatusCode:::',
      getDestinationStatusCode,
      getDestinationData?.payload,
    );

    // Get existence destinationId
    let destinationId;
    if (getDestinationStatusCode === 200 && getDestinationData?.payload?.length) {
      destinationId = getDestinationData?.payload?.find(
        (e: { name: string }) => e.name === NOTIFICATION_DESTINATION.NAME,
      )?.destinationId;
      console.log('🚀 ~ lambdaHandler ~ destinationId EXISTED:::::::', destinationId);
    }

    if (!destinationId) {
      const createdDestinationRes: any = await createDestination(grantlessAccessToken);
      destinationId = createdDestinationRes?.data;
      getDestinationStatusCode = createdDestinationRes?.status;
    }
    console.log('getDestinationStatusCode::::::::::::::', destinationId, getDestinationStatusCode);

    if (destinationId && getDestinationStatusCode === 200) {
      const getSubscriptionRes: any = await getSubscription(accessToken);
      const getSubscriptionStatusCode = getSubscriptionRes?.status;
      if (getSubscriptionStatusCode !== 200) {
        console.log(':::::::: CREATE SUBSCRIPTION :::::::::');

        // Subscribe to FEED_PROCESSING_FINISHED
        const createSubscriptionRes: any = await createSubscription(accessToken, destinationId);
        const createSubscriptionStatusCode = createSubscriptionRes?.status;
        if (createSubscriptionStatusCode === 200) {
          return successResponse(null, SUCCESS_MESSAGE.SUBSCRIBE_SUCCESS);
        }
      } else {
        return successResponse(null, ERROR_MESSAGE.SUBSCRIPTION_ALREADY_EXISTS);
      }
    }
    return successResponse(null, SUCCESS_MESSAGE.SUBSCRIBE_PROCESS_SUCCESS);
  } catch (err: any) {
    console.log(err);
    return errorResponse(null, err.message || ERROR_MESSAGE.INTERNAL_SERVER_ERROR);
  }
};

lambdaHandler();
