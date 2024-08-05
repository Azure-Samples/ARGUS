
#/bin/bash
docker build -f docker/frontend.Dockerfile -t aga-reg/aga-docextracionai-userapp .
docker push aga-reg/aga-docextracionai-userapp
docker build -f docker/backend.Dockerfile -t aga-reg/aga-docextracionai-backend .
docker push aga-reg/aga-docextracionai-backend