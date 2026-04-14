export const successResponse = (data = null, message = '', statusCode = 200) => {
  return {
    data,
    message,
    statusCode,
    isSuccess: true,
  };
};

export const errorResponse = (data = null, message = '', statusCode = 500) => {
  return {
    data,
    message,
    statusCode,
    isSuccess: false,
  };
};
