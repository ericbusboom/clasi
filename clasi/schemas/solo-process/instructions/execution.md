# Execution — solo-process

Execute tickets one at a time. For each ticket:

1. Set status to `in-progress` and acquire the execution lock.
2. Implement the acceptance criteria, write tests, and verify the test suite
   passes.
3. Mark all acceptance criteria checked and set status to `done`.
4. Release the execution lock before starting the next ticket.

The `per-ticket` gate fires automatically when a ticket is moved to done.
No team review is required — self-review is sufficient.
