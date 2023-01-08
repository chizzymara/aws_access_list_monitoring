# Serverless AWS Access List Monitoring.

This framework deploys a lambda function that sends emails IAM user information including permissions, groups, last
accessed times, in csv format, to specified email addresses.

## How it works

The python bot generates AWS IAM credential reports, Formats the report into python readable dictionary `content_dict` .

Logic within the format_msg(content_dict) function, formats the content of the initially empty `data_list` List which
will be converted to a csv file. First adding the headers of the `data_list`, and then getting the required information
for each user from content_dict, iam.list_access_keys() and iam.list_user_tags(). The information for each user is first
stored in `data`. The function then returns data_list a compilation of `data` for all the users with a header.

```
headers = "pt_user_name,pt_user_created_date,pt_password_last_used,pt_access_key_id,pt_access_key_created,pt_access_key_last_used,pt_user_groups,pt_user_policies,user_first_name,user_last_name,user_email, user_slack_id, user_type"
```

The write_csv(content_dict) function, creates `/tmp/data.csv` file and fills it with contents of `data_list`.

The message body is formatted in the attachment_msg(content_dict, receiver) function. The code is an excerpt from AWS
SES send raw email [documentation](https://docs.aws.amazon.com/ses/latest/dg/send-email-raw.html) . The email
includes `BODY_TEXT` and the `/tmp/data.csv` csv attachment.

The lambda function is scheduled to be triggered by Eventbridge every first day of the month at 11 am UTC. To change
this, edit the [serverless.yml](serverless.yml) file, entry `rate: cron(0 11 1 * ? *)`. AWS provides a
good [documentation](https://docs.aws.amazon.com/eventbridge/latest/userguide/eb-create-rule-schedule.html) for
formatting event rules.

## Requirements

- IAM users with standardized tags as follows:
    - `user:first_name` - first name for human users
    - `user:last_name` - last name for human users
    - `user:email` - email address
    - `user:slack_id` slack ID for human users
    - `user:type` - e.g. values of human and service.


- AWS SES configuration set must be created in the same region as the lambda function and the name of configuration set
  must be set as an environment variable in the serverless.yml  [file](/serverless.yml)
  . [Guide to create SES configuration set](https://docs.aws.amazon.com/ses/latest/dg/creating-configuration-sets.html)

- Sender and Receiver email address must be added and verified on
  SES. [Guide](https://docs.aws.amazon.com/ses/latest/dg/creating-identities.html#verify-email-addresses-procedure:~:text=of%20those%20Regions.-,Creating%20an%20email%20address%20identity,-Complete%20the%20following)
  to add and verify identities on SES. The sender email must be set as environment variable  `SENDER_EMAIL` . The
  receiver emails must be set in the environment variable `RECIPIENT_EMAIL_LIST` . If multiple separate by one space
  like so

```
RECIPIENT_EMAIL_LIST: 'somemail@gamil.com somemail@gamil.com'
```

Example of the functions section of the serverless.yml file showing rate and environment variables:

```
functions:
  aws_access_list:
    handler: functions/handler.lambda_handler
    events:
      - schedule:
	      name: Trigger_aws_access_list_monitoring
		  description: 'will trigger the aws bot lambda function every last monday of the month at 11am'
		  rate: cron(0 11 1 * ? *)
	environment:
	  RECIPIENT_EMAIL_LIST: 'somemail@gamil.com'
	  SENDER_EMAIL: 'somemail@gamil.com'
	  SES_CONFIGURATION_SET_NAME: 'aws-access-list-monitoring-prod'
role: AwsAccessListMonitoringLambdaRole
```

## Deployment

Deployment is done with Serverless framework

### Setup

Make sure `serverless` is
installed. [See installation guide](https://serverless.com/framework/docs/providers/openwhisk/guide/installation/).

You will also need to set up your AWS credentials using environment variables or a configuration file. Please see
the [this guide for more information](https://www.serverless.com/framework/docs/providers/aws/cli-reference/config-credentials)
.

### Deploy

`serverless deploy` or `sls deploy`. `sls` is shorthand for the Serverless CLI command. You can also specifify the aws
profile

`sls deploy --aws-profile <PROFILE_NAME>`

