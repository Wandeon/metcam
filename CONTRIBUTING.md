# Contributing to FootballVision Pro

## Development Process
1. Branch from `main` for each change.
2. Implement the update, focusing on the UI, recording, preview, or matches workflows.
3. Run the FastAPI server and verify the end-to-end flows manually:
   - Start/stop recording from the API or UI.
   - Launch/stop the preview stream.
   - Confirm completed matches appear in the matches tab and downloads succeed.
4. Update documentation when behaviour changes.
5. Submit a pull request with a short summary of the change and validation notes.

## Code Standards
- Python: PEP 8
- C++: Google Style Guide
- Git commits: Conventional Commits

## Testing Expectations
- Manual validation of the recording and preview pipelines is required.
- Add automated checks only when they directly support the current workflows.

## Documentation
- All public APIs must be documented
- README in each component directory
- Inline comments for complex logic
