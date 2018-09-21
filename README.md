# Browntruck (soon pypa-bot)

Bot(s) to help PyPA's working processes.

Together, [@pypa-bot](https://github.com/pypa-bot) and [@Browntruck](https://github.com/browntruck) handle:

- Checking that news file entries are added for PRs to pip
- Commenting and labelling PRs that can't be merged due to merge conflicts
- Dismissing reviews from maintainers based on request from PR authors

> NOTE: We're currently midway through porting the functionality to Twisted.
>
> This can be seen on the [twisted](https://github.com/pypa/browntruck/tree/twisted) branch. Some functionality (checking news entries, unlabelling merge conflict PRs) is handled by that branch currently.
