# GitHub Agent

AI-powered agent for GitHub repository management, Git operations, and Google Cloud Storage integration using Google's Agent Development Kit (ADK).


## Tools Overview

### GitHub Tools
| Tool | Purpose |
|------|---------|
| [`authenticate_github`](tools/github_api.py) | Verify GitHub API authentication |
| [`search_repositories`](tools/github_api.py) | Search GitHub repositories by keywords |
| [`list_branches`](tools/github_api.py) | List all branches in a repository |
| [`download_repository`](tools/github_api.py) | Download repository to local storage |
| [`download_repository_to_gcs`](tools/github_api.py) | Download repository directly to Google Cloud Storage |

### Git Tools
| Tool | Purpose |
|------|---------|
| [`initialize_git_repo`](tools/git_ops.py) | Initialize new Git repository |
| [`get_git_status`](tools/git_ops.py) | Check repository status and changes |
| [`add_files_to_git`](tools/git_ops.py) | Stage files for commit |
| [`commit_changes`](tools/git_ops.py) | Create commits with messages |
| [`list_git_branches`](tools/git_ops.py) | List all local branches |
| [`switch_git_branch`](tools/git_ops.py) | Switch or create branches |

### Google Cloud Storage Tools
| Tool | Purpose |
|------|---------|
| [`create_gcs_bucket`](tools/cloud_storage.py) | Create new GCS bucket |
| [`list_gcs_buckets`](tools/cloud_storage.py) | List all available buckets |
| [`delete_gcs_bucket`](tools/cloud_storage.py) | Delete bucket and contents |
| [`upload_repository_to_gcs`](tools/cloud_storage.py) | Upload repository as zip/directory |
| [`upload_directory_to_gcs`](tools/cloud_storage.py) | Upload local directory to bucket |
| [`download_from_gcs`](tools/cloud_storage.py) | Download files from bucket |
| [`list_gcs_objects`](tools/cloud_storage.py) | List objects in bucket |
| [`delete_from_gcs`](tools/cloud_storage.py) | Delete objects from bucket |

## Key Features

- 🔐 Secure GitHub authentication
- 📦 Repository download and management  
- 🌿 Branch operations and Git workflow
- ☁️ Direct GCS integration
- 🤖 AI-powered with Google ADK

## Security

- Keep `.env` file private
- Use minimal token permissions
- Rotate API keys regularly

## Support

- [Google ADK Docs](https://developers.google.com/adk)
- [GitHub API Docs](https://docs.github.com/en/rest)
