# Stage 1: Build the React application
FROM node:18-alpine AS build
WORKDIR /app

# Copy package files ONLY.
COPY package.json ./

# Install all dependencies from scratch.
RUN npm install

# Now, copy the rest of the application source code
COPY . .

# Run the standard build command
RUN npm run build

# Stage 2: Serve the static files with Nginx
FROM nginx:1.25-alpine
COPY --from=build /app/build /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
