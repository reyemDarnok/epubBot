import boto3


def upload_to_s3(filename: str, bucket_name: str):
    s3 = boto3.resource('s3')
    s3.meta.client.upload_file(filename, bucket_name, filename)
