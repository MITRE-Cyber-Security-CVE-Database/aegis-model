# AEGIS AWS GPU Training Infrastructure
# Uses AWS Educate / Free Tier + Spot instances for cost optimization
# Terraform configuration for GPU training environment

terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

# Use us-east-1 for best GPU spot availability
provider "aws" {
  region = var.aws_region
}

variable "aws_region" {
  description = "AWS region for deployment"
  default     = "us-east-1"
}

variable "key_name" {
  description = "EC2 Key Pair name for SSH access"
  default     = "aegis-gpu-key"
}

variable "instance_type" {
  description = "GPU instance type. g4dn.xlarge = cheapest GPU (T4)"
  default     = "g4dn.xlarge"  # $0.526/hour on-demand, ~$0.16/hour spot
}

variable "use_spot" {
  description = "Use spot instances for 70% cost savings"
  default     = true
}

variable "max_spot_price" {
  description = "Maximum spot price per hour"
  default     = "0.20"
}

# VPC
resource "aws_vpc" "aegis" {
  cidr_block           = "10.0.0.0/16"
  enable_dns_hostnames = true
  enable_dns_support   = true

  tags = {
    Name = "aegis-vpc"
    Project = "AEGIS"
  }
}

# Internet Gateway
resource "aws_internet_gateway" "aegis" {
  vpc_id = aws_vpc.aegis.id

  tags = {
    Name = "aegis-igw"
  }
}

# Public Subnet
resource "aws_subnet" "aegis_public" {
  vpc_id                  = aws_vpc.aegis.id
  cidr_block              = "10.0.1.0/24"
  availability_zone       = "${var.aws_region}a"
  map_public_ip_on_launch = true

  tags = {
    Name = "aegis-public-subnet"
  }
}

# Route Table
resource "aws_route_table" "aegis_public" {
  vpc_id = aws_vpc.aegis.id

  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.aegis.id
  }

  tags = {
    Name = "aegis-public-rt"
  }
}

resource "aws_route_table_association" "aegis_public" {
  subnet_id      = aws_subnet.aegis_public.id
  route_table_id = aws_route_table.aegis_public.id
}

# Security Group
resource "aws_security_group" "aegis_gpu" {
  name_prefix = "aegis-gpu-"
  vpc_id      = aws_vpc.aegis.id

  ingress {
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
    description = "SSH"
  }

  ingress {
    from_port   = 8888
    to_port     = 8888
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
    description = "Jupyter Notebook"
  }

  ingress {
    from_port   = 6006
    to_port     = 6006
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
    description = "TensorBoard"
  }

  ingress {
    from_port   = 11434
    to_port     = 11434
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
    description = "Ollama API"
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "aegis-gpu-sg"
  }
}

# Deep Learning AMI (pre-built with CUDA, PyTorch, etc.)
data "aws_ami" "deep_learning" {
  most_recent = true
  owners      = ["amazon"]

  filter {
    name   = "name"
    values = ["Deep Learning AMI GPU CUDA * (Ubuntu 22.04) *"]
  }

  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }
}

# Spot Instance Request (70% cheaper!)
resource "aws_spot_instance_request" "aegis_gpu" {
  count = var.use_spot ? 1 : 0

  ami                    = data.aws_ami.deep_learning.id
  instance_type          = var.instance_type
  key_name               = var.key_name
  vpc_security_group_ids = [aws_security_group.aegis_gpu.id]
  subnet_id              = aws_subnet.aegis_public.id

  spot_price             = var.max_spot_price
  wait_for_fulfillment   = true
  spot_type              = "one-time"

  root_block_device {
    volume_size = 256
    volume_type = "gp3"
  }

  user_data = <<-EOF
              #!/bin/bash
              # AEGIS GPU Setup
              apt-get update

              # Install Ollama
              curl -fsSL https://ollama.com/install.sh | sh

              # Setup workspace
              mkdir -p /home/ubuntu/aegis-model
              cd /home/ubuntu/aegis-model

              # Install additional Python packages
              pip install --upgrade transformers peft accelerate bitsandbytes datasets wandb

              # Auto-shutdown after 8 hours to save credits
              (sleep 28800 && shutdown -h now) &

              echo "AEGIS GPU spot instance ready at $(date)" > /home/ubuntu/setup.log
              EOF

  tags = {
    Name    = "aegis-gpu-spot"
    Project = "AEGIS"
    Type    = "spot-training"
  }
}

# On-Demand Instance (if spot not available)
resource "aws_instance" "aegis_gpu" {
  count = var.use_spot ? 0 : 1

  ami                    = data.aws_ami.deep_learning.id
  instance_type          = var.instance_type
  key_name               = var.key_name
  vpc_security_group_ids = [aws_security_group.aegis_gpu.id]
  subnet_id              = aws_subnet.aegis_public.id

  root_block_device {
    volume_size = 256
    volume_type = "gp3"
  }

  user_data = aws_spot_instance_request.aegis_gpu[0].user_data

  tags = {
    Name    = "aegis-gpu-ondemand"
    Project = "AEGIS"
    Type    = "ondemand-training"
  }
}

# S3 Bucket for model artifacts
resource "aws_s3_bucket" "aegis_models" {
  bucket = "cyberviser-aegis-models"

  tags = {
    Name    = "AEGIS Model Storage"
    Project = "AEGIS"
  }
}

resource "aws_s3_bucket_versioning" "aegis_models" {
  bucket = aws_s3_bucket.aegis_models.id
  versioning_configuration {
    status = "Enabled"
  }
}

# Budget Alarm (CRITICAL for student credits!)
resource "aws_budgets_budget" "aegis_monthly" {
  name              = "aegis-monthly-budget"
  budget_type       = "COST"
  limit_amount      = "50"
  limit_unit        = "USD"
  time_period_start = "2026-05-01_00:00"
  time_unit         = "MONTHLY"

  notification {
    comparison_operator        = "GREATER_THAN"
    threshold                  = 80
    threshold_type             = "PERCENTAGE"
    notification_type          = "ACTUAL"
    subscriber_email_addresses = ["johnny.watters@email.phoenix.edu"]
  }

  notification {
    comparison_operator        = "GREATER_THAN"
    threshold                  = 100
    threshold_type             = "PERCENTAGE"
    notification_type          = "ACTUAL"
    subscriber_email_addresses = ["johnny.watters@email.phoenix.edu"]
  }
}

# Outputs
output "instance_public_ip" {
  description = "Public IP of the GPU instance"
  value       = var.use_spot ? aws_spot_instance_request.aegis_gpu[0].public_ip : aws_instance.aegis_gpu[0].public_ip
}

output "ssh_command" {
  description = "SSH command to connect"
  value       = "ssh -i ~/.ssh/${var.key_name}.pem ubuntu@${var.use_spot ? aws_spot_instance_request.aegis_gpu[0].public_ip : aws_instance.aegis_gpu[0].public_ip}"
}

output "jupyter_url" {
  description = "Jupyter Notebook URL"
  value       = "http://${var.use_spot ? aws_spot_instance_request.aegis_gpu[0].public_ip : aws_instance.aegis_gpu[0].public_ip}:8888"
}

output "cost_note" {
  description = "Cost warning"
  value       = "Spot instance cost: ~$0.16/hour. On-demand: ~$0.53/hour. Auto-shutdown after 8 hours. Budget alarm at $50/month."
}

output "s3_bucket" {
  description = "S3 bucket for model artifacts"
  value       = aws_s3_bucket.aegis_models.bucket
}
