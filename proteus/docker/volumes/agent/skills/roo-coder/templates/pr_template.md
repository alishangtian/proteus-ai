# PR Template

## Summary

<!-- Describe what this PR does. Be specific about the changes made. -->
<!-- Include screenshots, GIFs, or videos for UI changes -->

### Changes Made
1. 
2. 
3. 

### Why These Changes?
<!-- Explain the rationale behind the changes -->

## Testing Instructions

### Prerequisites
- [ ] Node.js version: 
- [ ] Python version: 
- [ ] Database: 
- [ ] Other dependencies: 

### Steps to Test
1. Checkout this branch: `git checkout <branch-name>`
2. Install dependencies: `npm install` / `pip install -r requirements.txt`
3. Run tests: `npm test` / `pytest`
4. Start the application: `npm start` / `python app.py`
5. Verify the following:
   - [ ] Feature works as expected
   - [ ] No regression in existing functionality
   - [ ] Error handling is appropriate
   - [ ] Performance is acceptable

### Test Cases
| Test Case | Expected Result | Status |
|-----------|----------------|--------|
|           |                |        |
|           |                |        |
|           |                |        |

## Related Links

### Linear Ticket
<!-- Link to Linear ticket: https://linear.app/org/issue/TICKET-ID -->

### GitHub Issues
<!-- Use "closes #123", "fixes #456", or "resolves #789" to auto-close issues -->

### Documentation
<!-- Links to relevant documentation updates -->

## Checklist

### Before Review
- [ ] PR title follows conventional commit format
- [ ] Code is self-documented or comments are added
- [ ] No console.log/debug statements left
- [ ] No sensitive data exposed
- [ ] All new dependencies are necessary

### Code Quality
- [ ] Follows project coding standards
- [ ] No linting errors
- [ ] TypeScript/Flow types are correct (if applicable)
- [ ] No dead code or unused imports

### Testing
- [ ] Unit tests added/updated
- [ ] Integration tests added/updated
- [ ] End-to-end tests added/updated (if applicable)
- [ ] All tests pass
- [ ] Test coverage maintained or improved

### Security
- [ ] No security vulnerabilities introduced
- [ ] Input validation implemented
- [ ] Authentication/authorization handled properly
- [ ] No hardcoded secrets

### Performance
- [ ] No performance regressions
- [ ] Database queries optimized
- [ ] Large datasets handled appropriately
- [ ] Memory usage is reasonable

### Documentation
- [ ] README updated if needed
- [ ] API documentation updated
- [ ] Code comments added for complex logic
- [ ] Changelog updated (if project has one)

### Deployment
- [ ] Environment variables documented
- [ ] Database migrations included (if needed)
- [ ] Breaking changes documented
- [ ] Rollback plan considered

## Screenshots

<!-- Add before/after screenshots for UI changes -->

### Before
<!-- Screenshot of previous state -->

### After  
<!-- Screenshot of new state -->

## Additional Notes

<!-- Any other information reviewers should know -->

## Reviewers

<!-- Tag relevant reviewers -->
- @frontend-team 
- @backend-team
- @qa-team

---

*PR Template Version: 1.1*  
*Last Updated: 2024-01-01*
