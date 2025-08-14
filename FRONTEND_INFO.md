# Frontend Information

The frontend for this project is located in a separate repository/folder:
`C:\Users\Dhenenjay\eli-superconnector`

## Frontend Structure
- **landing/** - Next.js landing page
- **app/** - Main application
- **convex/** - Convex database integration

## Frontend Deployment

The frontend should be deployed separately to Vercel:

1. Navigate to the frontend directory:
   ```bash
   cd C:\Users\Dhenenjay\eli-superconnector\landing
   ```

2. Deploy to Vercel:
   ```bash
   npm install -g vercel
   vercel
   ```

3. Set environment variable for API URL:
   ```
   NEXT_PUBLIC_API_URL=https://your-backend.onrender.com
   ```

## Integration
After deploying both backend and frontend:
1. Update frontend environment variables to point to your backend API
2. Update CORS settings in backend to allow your frontend domain
3. Test the integration between frontend and backend
