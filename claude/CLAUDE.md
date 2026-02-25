# CLAUDE.md

You are an agent. Before doing anything else, determine which environment you are running in.

Check if you are on an EC2 instance by running:
```
curl -s --connect-timeout 2 http://169.254.169.254/latest/meta-data/instance-id
```

- If this returns a valid instance ID (starts with `i-`), you are on an EC2 instance. Read and follow [ec2/CLAUDE.md](ec2/CLAUDE.md).
- Otherwise, you are on a desktop/local machine. Read and follow [desktop/CLAUDE.md](desktop/CLAUDE.md).
