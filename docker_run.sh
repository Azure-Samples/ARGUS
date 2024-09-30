
#/bin/bash
docker build -f docker/frontend.Dockerfile -t abertaga27/aga-docextracionai-userapp:latest .
docker push abertaga27/aga-docextracionai-userapp:latest
docker build -f docker/backend.Dockerfile -t abertaga27/aga-docextracionai-backend:latest .
docker push abertaga27/aga-docextracionai-backend:latest