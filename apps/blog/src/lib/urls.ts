/** Same templates support the standalone blog and the site's /blog mount. */
export const blogUrl = (path = '/') => `${import.meta.env.BASE_URL.replace(/\/$/, '')}/${path.replace(/^\//, '')}`;
