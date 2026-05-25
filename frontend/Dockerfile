# Build stage
FROM node:22-alpine AS build
WORKDIR /app
COPY package.json ./
RUN npm install
COPY . .
ARG VITE_RAG_API_URL=http://localhost:8002
ARG VITE_DEMO_UI=false
ENV VITE_RAG_API_URL=$VITE_RAG_API_URL
ENV VITE_DEMO_UI=$VITE_DEMO_UI
RUN npm run build

# Serve static files
FROM nginx:1.25-alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
