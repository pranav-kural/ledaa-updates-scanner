variable "AWS_ACCESS_KEY" {}
variable "AWS_SECRET_KEY" {}
variable "LEDAA_LOAD_DATA_ARN" {
  description = "ARN of the ledaa_load_data Lambda function"
  type        = string
}