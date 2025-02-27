terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.76"
    }
  }

  required_version = ">= 1.5.6"
}

provider "aws" {
  region     = "ca-central-1"
  access_key = var.AWS_ACCESS_KEY
  secret_key = var.AWS_SECRET_KEY
}

resource "aws_iam_role" "lambda_role" {
  name = "ledaa_updates_scanner_lambda_role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Sid    = ""
        Principal = {
          Service = "lambda.amazonaws.com"
        }
      }
    ]
  })
}

resource "aws_iam_role_policy" "lambda_policy" {
  name = "ledaa_updates_scanner_lambda_policy"
  role = aws_iam_role.lambda_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents",
          "dynamodb:GetItem",
          "lambda:InvokeFunction"
        ]
        Effect   = "Allow"
        Resource = "*"
      },
      {
        Action   = "lambda:InvokeFunction"
        Effect   = "Allow"
        Resource = var.LEDAA_LOAD_DATA_ARN
      }
    ]
  })
}

resource "aws_lambda_layer_version" "lambda_layer" {
  filename         = "packages/ledaa_updates_scanner_lambda_layer.zip"
  layer_name       = "LEDAA-Updates-Scanner-Layer"
  source_code_hash = filebase64sha256("packages/ledaa_updates_scanner_lambda_layer.zip")

  compatible_runtimes = ["python3.13"]
}

data "archive_file" "lambda_code" {
  type        = "zip"
  source_file = "../core.py"
  output_path = "packages/ledaa_updates_scanner_package.zip"
}

resource "aws_lambda_function" "ledaa_updates_scanner" {
  function_name = "ledaa_updates_scanner_lambda"
  role          = aws_iam_role.lambda_role.arn
  handler       = "core.lambda_handler"
  runtime       = "python3.13"
  architectures = ["arm64"]

  filename         = "packages/ledaa_updates_scanner_package.zip"
  source_code_hash = data.archive_file.lambda_code.output_base64sha256

  layers = [aws_lambda_layer_version.lambda_layer.arn]

  timeout = 60
}

resource "aws_iam_role" "eventbridge_role" {
  name = "ledaa_updates_scanner_eventbridge_role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Service = "scheduler.amazonaws.com"
        }
        Action = "sts:AssumeRole"
      }
    ]
  })
}

resource "aws_iam_role_policy" "eventbridge_policy" {
  name = "ledaa_updates_scanner_eventbridge_policy"
  role = aws_iam_role.eventbridge_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = "lambda:InvokeFunction"
        Resource = aws_lambda_function.ledaa_updates_scanner.arn
      }
    ]
  })
}

resource "aws_scheduler_schedule" "ledaa_updates_scanner_schedule" {
  name                = "ledaa_updates_scanner_schedule"
  schedule_expression = "rate(1 day)"
  group_name          = "default"

  target {
    arn      = aws_lambda_function.ledaa_updates_scanner.arn
    role_arn = aws_iam_role.eventbridge_role.arn
  }

  flexible_time_window {
    mode = "OFF"
  }
}

resource "aws_lambda_permission" "allow_eventbridge_invoke" {
  statement_id  = "AllowExecutionFromEventBridge"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.ledaa_updates_scanner.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_scheduler_schedule.ledaa_updates_scanner_schedule.arn
}