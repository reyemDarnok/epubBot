import json
import logging
from typing import Dict, Any

from smart_open import smart_open


def upload_to_s3(filename: str):
    logger = logging.getLogger('aws')
    logger.info(f'Uploading {filename} to aws bucket')
    with smart_open(f's3://reyem-epub-bot-output/{filename}', 'wb') as fout:
        with smart_open(f'/tmp/{filename}', 'rb') as fin:
            for line in fin:
                fout.write(line)
    logger.debug(f'Finished uploading {filename} to aws bucket')


def get_config_from_s3() -> Dict[Any, Any]:
    logger = logging.getLogger('aws')
    logger.debug('Read config from s3 bucket')
    text = ''
    with smart_open('s3://reyem-epub-bot-config/config.json', 'rb') as s3_file:
        for line in s3_file:
            text += line.decode('utf8')
    logger.debug('Finished reading config from s3 bucket')
    return json.loads(text)