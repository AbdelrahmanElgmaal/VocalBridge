# Vocal Bridge Frontend

React + TypeScript frontend for the Vocal Bridge .NET 9 API.

## API Base URL

The Axios client defaults to:

```txt
https://localhost:5001
```

Override it with:

```txt
VITE_API_BASE_URL=https://your-api-host
```

## Wired Endpoints

- `POST /api/auth/register`
- `POST /api/auth/login`
- `POST /api/auth/refresh`
- `POST /api/videos/upload`
- `GET /api/videos`
- `GET /api/videos/{id}`
- `DELETE /api/videos/{id}`
- `POST /api/translations`
- `GET /api/translations`
- `GET /api/translations/{id}`
- `POST /api/translations/{id}/cancel`

Language controls are implemented in the UI. The current backend contract starts fixed English to Arabic jobs, so translation creation sends only `videoId` or `videoUrl` exactly as the .NET DTO requires.
