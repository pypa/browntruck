https://github.com/pypa-bot

The bot to help PyPA's working processes.

Currently, this handles:

- Checking that news file entries are added for pip
- Commenting and labelling PRs that can't be merged due to merge conflicts
- Dismissing reviews from maintainers based on request from PR authors

NOTE: We're currently midway through porting the functionality to Twisted. This can be seen on the [twisted](https://github.com/pypa/browntruck/tree/twisted) branch. Some functionality is handled by that branch currently.
