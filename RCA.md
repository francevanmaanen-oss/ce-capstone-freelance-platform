# Root cause analyses

Short write-ups of the issues I hit during the build and how I resolved them. Each follows the same structure: symptom, root cause, resolution, prevention.

---

## RCA 1 — App never started on new instances (indentation bug)

**Symptom**
After expanding the app into the FreelanceHub site, new instances launched by the Auto Scaling Group kept failing their ALB health checks. The instance refresh stalled at 33% with the message "is unhealthy. Resolve issues with failed health checks to continue," and the load balancer kept serving the previous version of the app.

**Root cause**
The Flask app is written onto each instance at boot by a script embedded in the launch template's user data. The app file was created with a here-document (`cat > app.py << 'PYEOF'`). Because the here-document sat inside Terraform's own indented heredoc, every line of the Python file landed on disk with four leading spaces. Python treats a leading indent on the first line as invalid, so the interpreter threw `IndentationError: unexpected indent` and the Flask service never started. With no app listening on port 5000, the `/health` endpoint never responded and the instances stayed unhealthy.

It passed local testing because I had stripped the indentation before running the syntax check, which hid the problem — the file I tested was not the file that actually landed on the instance.

**Resolution**
Changed the file-writing step from `cat` to `sed 's/^    //'`, which strips the four leading spaces from each line as the file is written. Applied the same change to the systemd service file. After re-applying and triggering a fresh instance refresh, the new instances started Flask cleanly, passed health checks, and the refresh moved past 33% to completion.

**Prevention**
Test user-data scripts exactly as they will be written on the instance, with indentation intact, rather than a hand-cleaned copy. An even more robust approach would be to keep the application code in its own file in the repository and have the instance download it at boot, removing the nested-heredoc indentation problem entirely.

---

## RCA 2 — First terraform apply failed on RDS

**Symptom**
The initial `terraform apply` failed partway through with `FreeTierRestrictionError: The specified backup retention period exceeds the maximum available to free tier customers`. The database was not created.

**Root cause**
The RDS instance was configured with `backup_retention_period = 7`. AWS Free Tier accounts do not permit automated backup retention above the free-tier limit, so the CreateDBInstance call was rejected.

**Resolution**
Set `backup_retention_period = 0` to disable automated backups, which is permitted on free tier. Re-ran apply and the database created successfully.

**Prevention**
Check free-tier service limits before setting values that assume a paid account. For production this would be set back to 7 or more days; the choice to use 0 is documented as a deliberate, environment-specific trade-off rather than an oversight.

---

## RCA 3 — CloudWatch dashboard failed to create

**Symptom**
`terraform apply` failed when creating the CloudWatch dashboard, returning twelve validation errors all variations of "Should have required property 'region'" and "The metric widget should have specified a region."

**Root cause**
Each metric widget in a CloudWatch dashboard body must declare which region its metrics come from. The original dashboard JSON defined the metrics and titles but omitted the `region` property on every widget, so the PutDashboard API rejected the whole body.

**Resolution**
Added `region = "eu-central-1"` to the properties of every widget, and laid the four widgets out in a 2x2 grid while making the change. The dashboard then created without error.

**Prevention**
When building CloudWatch dashboard JSON by hand, include `region` on every metric widget from the start. Validating the dashboard body against the API's requirements before applying would have caught this earlier.

---

## RCA 4 — Instance refresh did not roll out the new app automatically

**Symptom**
After updating the application and running `terraform apply`, the running instances kept serving the old version. Checking the Auto Scaling Group showed no instance refresh had ever started (`describe-instance-refreshes` returned None), even though the launch template had been updated.

**Root cause**
Updating a launch template does not by itself replace running instances — the Auto Scaling Group keeps the existing instances until something triggers a replacement. The `instance_refresh` block only triggers a rolling refresh when Terraform detects the launch template change during an apply. Because the template update and the addition of the `instance_refresh` block landed in a way that didn't trigger the refresh, the old instances kept running untouched.

**Resolution**
Triggered the refresh manually with `aws autoscaling start-instance-refresh`, which rolled all instances and replaced them with new ones pulling the current launch template. Confirmed progress with `describe-instance-refreshes` and target health checks until all instances were healthy on the new version.

**Prevention**
Understand that a launch template change is not self-deploying — a refresh (automatic via the `instance_refresh` trigger, or manual) is always required to roll it out. When in doubt, verify the deployed launch template's user data directly and check the target group health rather than assuming an apply pushed the change live.


Symptom: CloudWatch alarms transitioned to ALARM but no notification email arrived.
Root cause: The SNS topic was encrypted with the AWS-managed KMS key (alias/aws/sns), added to satisfy a tfsec finding. The AWS-managed SNS key does not grant CloudWatch permission to use it, so every publish failed with "CloudWatch Alarms does not have authorization to access the SNS topic encryption key." Confirmed via the alarm history action data; a direct aws sns publish succeeded, isolating the failure to the CloudWatch→encrypted-topic path.
Resolution: Removed encryption from the SNS topic (alerts carry non-sensitive operational data), suppressed the tfsec finding with documented justification. Action state changed to "Succeeded" and email delivery confirmed.
Prevention: When encrypting SNS topics that receive CloudWatch alarm notifications, use a customer-managed KMS key with a policy granting CloudWatch (cloudwatch.amazonaws.com) kms:GenerateDataKey and kms:Decrypt — or omit encryption for non-sensitive operational topics.