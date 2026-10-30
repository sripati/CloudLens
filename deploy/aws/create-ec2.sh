#!/bin/bash
# Create a staging EC2 instance for CloudLens with the AWS CLI.
#
# Prerequisites: AWS CLI v2 configured (aws configure), an existing EC2 key pair.
# Usage:  KEY_NAME=my-key ./deploy/aws/create-ec2.sh
#
# Creates: security group (SSH from your IP only, HTTP 80 from anywhere), IAM role + instance
# profile with the read-only CloudLens policy, and one t3.small instance (Amazon Linux 2023).
set -euo pipefail

REGION=${AWS_REGION:-ap-south-1}
KEY_NAME=${KEY_NAME:?set KEY_NAME to an existing EC2 key pair name}
INSTANCE_TYPE=${INSTANCE_TYPE:-t3.small}
NAME=${NAME:-cloudlens-staging}
HERE=$(cd "$(dirname "$0")" && pwd)
MY_IP=$(curl -fsS https://checkip.amazonaws.com)/32

echo "Region: $REGION  Type: $INSTANCE_TYPE  SSH allowed from: $MY_IP"

VPC_ID=$(aws ec2 describe-vpcs --region "$REGION" --filters Name=isDefault,Values=true --query 'Vpcs[0].VpcId' --output text)
SG_ID=$(aws ec2 describe-security-groups --region "$REGION" --filters Name=group-name,Values="$NAME-sg" Name=vpc-id,Values="$VPC_ID" \
  --query 'SecurityGroups[0].GroupId' --output text 2>/dev/null || true)
if [ "$SG_ID" = "None" ] || [ -z "$SG_ID" ]; then
  SG_ID=$(aws ec2 create-security-group --region "$REGION" --group-name "$NAME-sg" --description "CloudLens dashboard" --vpc-id "$VPC_ID" --query GroupId --output text)
  aws ec2 authorize-security-group-ingress --region "$REGION" --group-id "$SG_ID" --protocol tcp --port 22 --cidr "$MY_IP"
  aws ec2 authorize-security-group-ingress --region "$REGION" --group-id "$SG_ID" --protocol tcp --port 80 --cidr 0.0.0.0/0
fi

ROLE=$NAME-role
if ! aws iam get-role --role-name "$ROLE" >/dev/null 2>&1; then
  aws iam create-role --role-name "$ROLE" --assume-role-policy-document '{
    "Version":"2012-10-17","Statement":[{"Effect":"Allow","Principal":{"Service":"ec2.amazonaws.com"},"Action":"sts:AssumeRole"}]}' >/dev/null
  aws iam put-role-policy --role-name "$ROLE" --policy-name cloudlens-read --policy-document "file://$HERE/iam-policy.json"
  aws iam create-instance-profile --instance-profile-name "$ROLE" >/dev/null
  aws iam add-role-to-instance-profile --instance-profile-name "$ROLE" --role-name "$ROLE"
  sleep 10  # IAM propagation
fi

AMI=$(aws ssm get-parameter --region "$REGION" --name /aws/service/ami-amazon-linux-latest/al2023-ami-kernel-default-x86_64 --query Parameter.Value --output text)

INSTANCE_ID=$(aws ec2 run-instances --region "$REGION" --image-id "$AMI" --instance-type "$INSTANCE_TYPE" \
  --key-name "$KEY_NAME" --security-group-ids "$SG_ID" --iam-instance-profile Name="$ROLE" \
  --block-device-mappings '[{"DeviceName":"/dev/xvda","Ebs":{"VolumeSize":20,"VolumeType":"gp3","DeleteOnTermination":true}}]' \
  --metadata-options HttpTokens=required \
  --user-data "file://$HERE/ec2-user-data.sh" \
  --tag-specifications "ResourceType=instance,Tags=[{Key=Name,Value=$NAME},{Key=environment,Value=staging},{Key=project,Value=cloudlens}]" \
  --query 'Instances[0].InstanceId' --output text)

echo "Waiting for $INSTANCE_ID ..."
aws ec2 wait instance-running --region "$REGION" --instance-ids "$INSTANCE_ID"
IP=$(aws ec2 describe-instances --region "$REGION" --instance-ids "$INSTANCE_ID" --query 'Reservations[0].Instances[0].PublicIpAddress' --output text)
echo
echo "Instance ready: $INSTANCE_ID  public IP: $IP"
echo "Next:  EC2_HOST=$IP SSH_KEY=~/.ssh/$KEY_NAME.pem ./deploy/aws/deploy.sh"
