########################################
# VPC – base network for Fake-Fintech #
########################################
########################
# Input configuration  #
########################
variable "project"            { type = string  }
variable "environment"         { type = string  }
variable "region"              { type = string  }
variable "vpc_cidr"            { type = string  }
variable "azs"                 { type = list(string) }
variable "public_subnet_cidrs" { type = list(string) }
variable "private_subnet_cidrs"{ type = list(string) }

##################
# Tag generator  #
##################
locals {
  common_tags = {
    Project     = var.project
    Environment = var.environment
    Terraform   = "true"
  }
}

#############
#   VPC     #
#############
resource "aws_vpc" "main" {
  cidr_block           = var.vpc_cidr
  enable_dns_hostnames = true
  enable_dns_support   = true

  tags = merge(local.common_tags, {
    Name = "${var.project}-${var.environment}-vpc"
  })
}

#############################
# Internet Gateway (IGW)    #
#############################
resource "aws_internet_gateway" "igw" {
  vpc_id = aws_vpc.main.id

  tags = merge(local.common_tags, {
    Name = "${var.project}-${var.environment}-igw"
  })
}

######################
# Public Subnets     #
######################
resource "aws_subnet" "public" {
  for_each = {
    for idx, cidr in var.public_subnet_cidrs :
    idx => {
      cidr = cidr
      az   = element(var.azs, idx)
    }
  }

  vpc_id                  = aws_vpc.main.id
  cidr_block              = each.value.cidr
  availability_zone       = each.value.az
  map_public_ip_on_launch = true

  tags = merge(local.common_tags, {
    Name = "${var.project}-${var.environment}-public-${each.key}"
    Tier = "public"
  })
}

#######################
# Private Subnets     #
#######################
resource "aws_subnet" "private" {
  for_each = {
    for idx, cidr in var.private_subnet_cidrs :
    idx => {
      cidr = cidr
      az   = element(var.azs, idx)
    }
  }

  vpc_id            = aws_vpc.main.id
  cidr_block        = each.value.cidr
  availability_zone = each.value.az

  tags = merge(local.common_tags, {
    Name = "${var.project}-${var.environment}-private-${each.key}"
    Tier = "private"
  })
}

######################################
# Elastic IP for NAT (one per AZ)    #
######################################
resource "aws_eip" "nat_eip" {
  for_each = aws_subnet.public

  vpc = true

  depends_on = [aws_internet_gateway.igw]

  tags = merge(local.common_tags, {
    Name = "${var.project}-${var.environment}-nat-eip-${each.key}"
  })
}

##################
# NAT Gateways   #
##################
resource "aws_nat_gateway" "nat" {
  for_each = aws_subnet.public

  allocation_id = aws_eip.nat_eip[each.key].id
  subnet_id     = aws_subnet.public[each.key].id

  tags = merge(local.common_tags, {
    Name = "${var.project}-${var.environment}-nat-${each.key}"
  })
}

##############################
# Route Tables –  Public     #
##############################
resource "aws_route_table" "public" {
  vpc_id = aws_vpc.main.id

  tags = merge(local.common_tags, {
    Name = "${var.project}-${var.environment}-public-rt"
    Tier = "public"
  })
}

resource "aws_route" "public_internet_access" {
  route_table_id         = aws_route_table.public.id
  destination_cidr_block = "0.0.0.0/0"
  gateway_id             = aws_internet_gateway.igw.id
}

resource "aws_route_table_association" "public_assoc" {
  for_each       = aws_subnet.public
  subnet_id      = each.value.id
  route_table_id = aws_route_table.public.id
}

###############################
# Route Tables –  Private     #
###############################
resource "aws_route_table" "private" {
  for_each = aws_nat_gateway.nat

  vpc_id = aws_vpc.main.id

  tags = merge(local.common_tags, {
    Name = "${var.project}-${var.environment}-private-rt-${each.key}"
    Tier = "private"
  })
}

resource "aws_route" "private_egress" {
  for_each               = aws_route_table.private
  route_table_id         = each.value.id
  destination_cidr_block = "0.0.0.0/0"
  nat_gateway_id         = aws_nat_gateway.nat[each.key].id
}

resource "aws_route_table_association" "private_assoc" {
  for_each = {
    # Map each private subnet to the RT in its AZ
    for key, subnet in aws_subnet.private :
    key => {
      subnet_id      = subnet.id
      route_table_id = aws_route_table.private[key].id
    }
  }

  subnet_id      = each.value.subnet_id
  route_table_id = each.value.route_table_id
}

###########
# Outputs #
###########
output "vpc_id" {
  value = aws_vpc.main.id
}

output "public_subnet_ids" {
  value = [for s in aws_subnet.public : s.id]
}

output "private_subnet_ids" {
  value = [for s in aws_subnet.private : s.id]
}