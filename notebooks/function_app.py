import azure.functions as func
import logging
import traceback
import os
import json
import random
from datetime import datetime
import tempfile
import base64
from pathlib import Path
from dotenv import load_dotenv

from cosmosdb_utils import CosmosDBManager
from request_log import RequestLog

from ai_ocr.chains import get_structured_data, get_final_reasoning_from_markdown
from ai_ocr.process import process_pdf

app = func.FunctionApp(http_auth_level=func.AuthLevel.FUNCTION)

@app.route(route="process_claims")
def claims_http_trigger(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('process_claims function processed a request.')

    load_dotenv()

    try:
        #Handling POST: request processing
        if req.method == 'POST':
            timer_start = datetime.now()
            req_body = req.get_json()
            
            file_name = req_body.get('file_name')
            logging.info(f"json file name received: {file_name}")
            file_content = req_body.get('file_content')

            #Decode the file content and write a temp file
            file_dec = base64.b64decode(file_content)
            with open('output_temp', 'wb') as file_to_write:
                file_to_write.write(file_dec)          
            input_path = os.path.join(Path('output_temp').parent.absolute(),'output_temp')
            #logging.info('after encoding')

            prompt = req_body.get('system_prompt')
            
            json_schema = req_body.get('json_schema')
            logging.info(json_schema)
            
            ocr_response = process_pdf(file_to_ocr=input_path,
                        prompt=prompt,
                        json_schema=json_schema)
            #logging.info(f'Response: {ocr_response}')
            
            nl_reponse = get_final_reasoning_from_markdown(ocr_response)
            #logging.info(f"NL Response: {nl_reponse}")

            classification = 'N/A'
            try:
                classification = ocr_response.categorization
            
            except:
                logging.warn("Cannot find 'categorization' in output schema! Logging it as N/A...")

            timer_stop = datetime.now()

            #TODO evaluator + accuracy logging
            # 1. start a new timer for evaluator
            # 2. call the evaluator
            accuracy = 0

            #Save in CosmosDB (system requests history)
            db = CosmosDBManager()
            request_id =  str(random.randint(10000000, 99999999))
            request_data  = RequestLog(
                request_id=request_id,
                request_filename=file_name,
                request_timestamp=timer_start,
                total_time_seconds=(timer_stop - timer_start).total_seconds(),
                classification=classification,
                accuracy=accuracy,
                model_output=json.dumps(nl_reponse.content)
            )
            db.create_system_request(request_id, request_data.to_dict())

            #Combining final response
            dictA = json.loads(ocr_response)
            dictB = json.dumps(nl_reponse.content)

            final_response = {}
            final_response["ocr_response"] = json.dumps(dictA)
            final_response["nl_response"] = dictB

            logging.info(f"Final Response: {final_response}")
            
            return func.HttpResponse(json.dumps(final_response),
                    status_code=200
            )
        else:
            #Handling GET: load requests history
            if req.method == 'GET':
                body = req.get_json()
                size = body.get("size")
                db = CosmosDBManager()
                history = db.list_all_requests(size)
                return func.HttpResponse(json.dumps(history),
                    status_code=200
                )    

    except:
        logging.error("error occurred in function process_claims")
        logging.error(traceback.format_exc())
        return func.HttpResponse("Function in error",
            #response.content,
            status_code=500
        )
        
    