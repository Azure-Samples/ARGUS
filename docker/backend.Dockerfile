# To enable ssh & remote debugging on app service change the base image to the one below
# FROM mcr.microsoft.com/azure-functions/python:4-python3.9-appservice
FROM mcr.microsoft.com/azure-functions/python:4-python3.11

ENV AzureWebJobsScriptRoot=/home/site/wwwroot \
    AzureFunctionsJobHost__Logging__Console__IsEnabled=true \
    AzureWebJobsFeatureFlags=EnableWorkerIndexing

COPY ./backend/requirements.txt /
RUN pip install -r /requirements.txt

COPY ./backend /home/site/wwwroot

RUN ln -sf /usr/share/zoneinfo/Europe/Rome /etc/localtime