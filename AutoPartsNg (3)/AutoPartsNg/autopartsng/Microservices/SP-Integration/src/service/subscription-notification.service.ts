import axios from 'axios';
import { NOTIFICATION_DESTINATION, SP_API_URL } from '../constants/sp.constants';
import { FEED_PROCESSING_SQS_ARN, SP_APP_CLIENT_ID, SP_APP_CLIENT_SECRET } from '../config/env.config';

// Get Destination
export const getLwaToken = async (grantType: string, extraParams = {}) => {
  let accessToken;
  let getLwaStatusCode;
  try {
    const params = new URLSearchParams({
      grant_type: grantType,
      client_id: SP_APP_CLIENT_ID,
      client_secret: SP_APP_CLIENT_SECRET,
      ...extraParams,
    }).toString();

    const { data } = await axios.post(SP_API_URL.LWA_TOKEN_URL, params, {
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    });

    accessToken = data.access_token;
  } catch (error: any) {
    accessToken = undefined;
    getLwaStatusCode = error?.status;
  }
  return { data: accessToken, status: getLwaStatusCode };
};

// Get Destination
export const getDestination = async (grantlessAccessToken: string) => {
  let getDestinationData;
  let getDestinationStatusCode;
  try {
    const getDestinationRes = await axios.get(SP_API_URL.CREATE_DESTINATION, {
      headers: { 'x-amz-access-token': grantlessAccessToken },
    });
    console.log('🚀 ~ lambdaHandler ~ getDestinationRes::::', getDestinationRes?.data);
    getDestinationData = getDestinationRes?.data;
    getDestinationStatusCode = getDestinationRes?.status;
  } catch (error: any) {
    getDestinationData = undefined;
    getDestinationStatusCode = error?.status;
  }
  return { data: getDestinationData, status: getDestinationStatusCode };
};

// Create Destination
export const createDestination = async (grantlessAccessToken: string) => {
  let destinationId;
  let getDestinationStatusCode;
  try {
    const destination = await axios.post(
      SP_API_URL.CREATE_DESTINATION,
      { resourceSpecification: { sqs: { arn: FEED_PROCESSING_SQS_ARN } }, name: NOTIFICATION_DESTINATION.NAME },
      { headers: { 'x-amz-access-token': grantlessAccessToken } },
    );
    console.log('🚀 ~ createDestination ~ FEED_PROCESSING_SQS_ARN::::', FEED_PROCESSING_SQS_ARN);
    console.log('🚀 ~ lambdaHandler ~ destination::::', destination.data);

    destinationId = destination?.data?.payload?.destinationId;
    getDestinationStatusCode = destination.status;
    console.log('🚀 ~ lambdaHandler ~ destinationId CREATED::::', destinationId);
  } catch (error: any) {
    destinationId = undefined;
    getDestinationStatusCode = error.status;
  }
  return { data: destinationId, status: getDestinationStatusCode };
};

// Get Subscription
export const getSubscription = async (accessToken: string) => {
  let getSubscriptionStatusCode;
  try {
    const subscriptions = await axios.get(`${SP_API_URL.CREATE_SUBSCRIPTION}/FEED_PROCESSING_FINISHED`, {
      headers: { 'x-amz-access-token': accessToken },
    });
    console.log('🚀 ~ lambdaHandler ~ subscriptions::::', subscriptions.data);
    getSubscriptionStatusCode = subscriptions.status;
  } catch (error: any) {
    getSubscriptionStatusCode = error.status;
  }
  return { status: getSubscriptionStatusCode };
};

// Create Subscription
export const createSubscription = async (accessToken: string, destinationId: string) => {
  let createSubscriptionStatusCode;
  try {
    // Subscribe to FEED_PROCESSING_FINISHED
    const createdSubscription = await axios.post(
      `${SP_API_URL.CREATE_SUBSCRIPTION}/FEED_PROCESSING_FINISHED`,
      {
        payloadVersion: '1.0',
        destinationId,
      },
      { headers: { 'x-amz-access-token': accessToken } },
    );
    console.log('🚀 ~ lambdaHandler ~ createdSubscription::::', createdSubscription.data);
    createSubscriptionStatusCode = createdSubscription.status;
  } catch (error: any) {
    createSubscriptionStatusCode = error.status;
  }
  return { status: createSubscriptionStatusCode };
};
