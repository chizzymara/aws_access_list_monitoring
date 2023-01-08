import csv
import logging
import os
import boto3
import time
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication

IAM = boto3.client('iam')
RECIPIENT_EMAIL_LIST = os.environ['RECIPIENT_EMAIL_LIST'].split(" ")
SENDER_EMAIL = os.environ['SENDER_EMAIL']
SES_CONFIGURATION_SET_NAME = os.environ['SES_CONFIGURATION_SET_NAME']


class ExceptionGenerateReport(Exception):
    pass


class ExceptionFormatReport(Exception):
    pass


class NoSuchEntityException(Exception):
    pass


class ExceptionGetReport(Exception):
    pass


def lambda_handler(event, context):
    report = generate_report()
    for attempt in range(10):
        try:
            decoded_content = get_report(report)
        except:
            time.sleep(1)
            continue
        else:
            break
    format_report(decoded_content, report)
    content_dict = format_report(decoded_content, report)
    format_msg(content_dict)
    write_csv(content_dict)

    for receiver in RECIPIENT_EMAIL_LIST:
        attachment_msg(content_dict, receiver)


def generate_report():
    try:
        report = IAM.generate_credential_report()
        return report
    except Exception as exc:
        logging.exception(exc)
        raise ExceptionGenerateReport from exc


def get_report(report):
    try:
        content = IAM.get_credential_report()
        # convert from bytes to string
        decoded_content = content["Content"].decode("utf-8")
        return decoded_content
    except Exception as exc:
        logging.exception(exc)
        raise ExceptionGetReport from exc


def format_report(decoded_content, report):
    try:
        decoded_content = get_report(report)
        content_lines = decoded_content.split("\n")

        # Initiate the reader, convert that to a list and turn that into a dict
        content_reader = csv.DictReader(content_lines, delimiter=",")
        content_dict = dict(enumerate(list(content_reader)))

        return content_dict
    except Exception as exc:
        logging.exception(exc)
        raise ExceptionFormatReport from exc


def format_msg(content_dict):
    data_list = []
    headers = "pt_user_name,pt_user_created_date,pt_password_last_used,pt_access_key_id,pt_access_key_created,pt_access_key_last_used,pt_user_groups,pt_user_policies,user_first_name,user_last_name,user_email, user_slack_id, user_type"
    data_list.append(headers)

    for user in content_dict:
        pt_user_name = content_dict[user]['user'].strip("<>")
        pt_user_created_date = content_dict[user]['user_creation_time']
        pt_password_last_used = content_dict[user]['password_last_used']

        try:
            pt_user_groups = [group['GroupName'] for groups_page in
                              IAM.get_paginator('list_groups_for_user').paginate(UserName=pt_user_name) for group in
                              groups_page['Groups']]
        except:
            pt_user_groups = "-"

        pt_user_policies = list()
        try:
            for policies_page in IAM.get_paginator('list_user_policies').paginate(UserName=pt_user_name):
                pt_user_policies += policies_page['PolicyNames']

        except:
            pt_user_policies = "-"

        try:
            tag_dict = IAM.list_user_tags(UserName=pt_user_name)
            for tags in tag_dict["Tags"]:
                if tags['Key'] == 'user:first_name':
                    user_first_name = tags['Value']
                elif tags['Key'] == 'user:last_name':
                    user_last_name = tags['Value']
                elif tags['Key'] == 'user:email':
                    user_email = tags['Value']
                elif tags['Key'] == 'user:slack_id':
                    user_slack_id = tags['Value']
                elif tags['Key'] == 'user:type':
                    user_type = tags['Value']

        except Exception as exc:
            logging.exception(exc)
            user_first_name = user_last_name = user_email = user_slack_id = user_type = "Not applicable"

        if content_dict[user]['access_key_1_active'] == 'true':
            for access_key in IAM.list_access_keys(UserName=pt_user_name)['AccessKeyMetadata']:
                pt_access_key_id = access_key['AccessKeyId']
                pt_access_key_created = access_key['CreateDate']
                access_key_last_used = IAM.get_access_key_last_used(AccessKeyId=access_key['AccessKeyId'])

                try:
                    pt_access_key_last_used = access_key_last_used['AccessKeyLastUsed']['LastUsedDate']
                except KeyError:
                    pt_access_key_last_used = 'Never'

                data = '"{}","{}","{}","{}","{}","{}","{}","{}","{}","{}","{}","{}","{}"'.format(pt_user_name,
                                                                                                 pt_user_created_date,
                                                                                                 pt_password_last_used,
                                                                                                 pt_access_key_id,
                                                                                                 pt_access_key_created,
                                                                                                 pt_access_key_last_used,
                                                                                                 ','.join(
                                                                                                     pt_user_groups),
                                                                                                 ','.join(
                                                                                                     pt_user_policies),
                                                                                                 user_first_name,
                                                                                                 user_last_name,
                                                                                                 user_email,
                                                                                                 user_slack_id,
                                                                                                 user_type)
                data_list.append(data)

        elif content_dict[user]['access_key_1_active'] == 'false':
            pt_access_key_id = "Not applicable"
            pt_access_key_last_used = 'Never'
            pt_access_key_created = "Never"
            data = '"{}","{}","{}","{}","{}","{}","{}","{}","{}","{}","{}","{}","{}"'.format(pt_user_name,
                                                                                             pt_user_created_date,
                                                                                             pt_password_last_used,
                                                                                             pt_access_key_id,
                                                                                             pt_access_key_created,
                                                                                             pt_access_key_last_used,
                                                                                             ','.join(pt_user_groups),
                                                                                             ','.join(pt_user_policies),
                                                                                             user_first_name,
                                                                                             user_last_name, user_email,
                                                                                             user_slack_id, user_type)
            data_list.append(data)

        print(data_list)
    return data_list


def write_csv(content_dict):
    data_list = format_msg(content_dict)
    my_file = open('/tmp/data.csv', 'w')
    for row in data_list:
        my_file.write(row)
        my_file.write('\n')
    my_file.close()
    return my_file


## piece of code gotten from aws ses send raw email documentaion (https://docs.aws.amazon.com/ses/latest/dg/send-email-raw.html)
def attachment_msg(content_dict, receiver):
    write_csv(content_dict)
    ses_client = boto3.client('ses')
    SENDER = SENDER_EMAIL
    RECEIVER = receiver

    CHARSET = "utf-8"
    msg = MIMEMultipart('mixed')
    msg['Subject'] = "AWS user summary"
    msg['From'] = SENDER
    msg['To'] = RECEIVER

    msg_body = MIMEMultipart('alternative')
    # text based email body
    BODY_TEXT = "Dear,\n\rHere is a summary of PROD aws account users."
    textpart = MIMEText(BODY_TEXT.encode(CHARSET), 'plain', CHARSET)

    msg_body.attach(textpart)

    # Full path to the file that will be attached to the email.
    ATTACHMENT1 = "/tmp/data.csv"

    # Adding attachments
    att1 = MIMEApplication(open(ATTACHMENT1, 'rb').read())
    att1.add_header('Content-Disposition', 'attachment',
                    filename=os.path.basename(ATTACHMENT1))
    msg.attach(msg_body)
    msg.attach(att1)

    try:
        response = ses_client.send_raw_email(
            Source=SENDER,
            Destinations=[
                RECEIVER
            ],
            RawMessage={
                'Data': msg.as_string(),
            },
            ConfigurationSetName=SES_CONFIGURATION_SET_NAME
        )
        print("Message id : ", response['MessageId'])
        print("Message send successfully!")
    except Exception as e:
        print("Error: ", e)
