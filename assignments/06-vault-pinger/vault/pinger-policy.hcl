# KV v2 adds /data/ between the mount point and the logical secret path.
# With the token of created policy we can only read
path "secret/data/pinger/database" {
  capabilities = ["read"]
}
