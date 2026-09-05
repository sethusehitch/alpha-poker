output "instance_name" {
  value = aws_lightsail_instance.app.name
}

output "public_ip" {
  value = aws_lightsail_static_ip.app.ip_address
}

output "temporary_hostname" {
  value = "alpha-poker.${aws_lightsail_static_ip.app.ip_address}.sslip.io"
}

output "primary_hostname" {
  value = var.domain_name
}

output "www_hostname" {
  value = "www.${var.domain_name}"
}

output "site_url" {
  value = "https://${var.domain_name}"
}

output "ssh_user" {
  value = aws_lightsail_instance.app.username
}
