workflow "On push" {
  on = "push"
  resolves = ["Chronographer"]
}

workflow "On PR" {
  on = "pull_request"
  resolves = ["Chronographer"]
}

action "Chronographer" {
  uses = "sanitizers/chronographer-github-app@master"
}
