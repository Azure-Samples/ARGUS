## ARGUS Processing Options Feature Test Plan

### Backend Validation ✅
- Backend is healthy and running: ✅
- API endpoints are accessible: ✅
- Configuration endpoint returns data: ✅

### Frontend UI Testing (Manual Steps)

#### 1. Access the Frontend
- URL: https://ca-frontend-fq3yxgwo7hqn4.jollyriver-a6fa0b27.eastus2.azurecontainerapps.io
- Verify the main interface loads correctly

#### 2. Test Dataset Configuration
Navigate to the dataset configuration section and verify:
- [ ] Processing options checkboxes are visible
- [ ] Four options are available:
  - [ ] Include OCR text in GPT extraction
  - [ ] Include images in GPT extraction  
  - [ ] Enable summary generation
  - [ ] Enable evaluation/enrichment
- [ ] Help/explanation text is available
- [ ] Cost/performance feedback is shown
- [ ] Options can be toggled on/off

#### 3. Test "Add New Dataset" Form
- [ ] Processing options are available in the new dataset form
- [ ] Default values are appropriate
- [ ] All options can be configured before saving

#### 4. Test Processing Pipeline
Create test scenarios with different option combinations:

##### Scenario 1: Minimal Processing
- Options: All disabled (OCR: ❌, Images: ❌, Summary: ❌, Evaluation: ❌)
- Upload: sample-invoice.pdf
- Expected: Basic extraction only, faster processing, lower cost

##### Scenario 2: OCR Only
- Options: OCR: ✅, Images: ❌, Summary: ❌, Evaluation: ❌
- Upload: sample-invoice.pdf
- Expected: GPT extraction includes OCR text

##### Scenario 3: Full Processing
- Options: All enabled (OCR: ✅, Images: ✅, Summary: ✅, Evaluation: ✅)
- Upload: sample-invoice.pdf
- Expected: Complete processing pipeline with all features

### Test Documents Available
- `/Users/konstantinos/Code/argus-testing/ARGUS/sample-invoice.pdf`
- `/Users/konstantinos/Code/argus-testing/ARGUS/demo/default-dataset/Invoice Sample.pdf`

### Backend Processing Logic ✅
The following backend changes were implemented and deployed:
- `ai_ocr/process.py`: Updated to handle processing_options
- `main.py`: Modified processing pipeline to conditionally execute steps
- Error handling and logging updated for conditional execution

### Frontend UI Changes ✅
The following frontend changes were implemented and deployed:
- Added processing option checkboxes to dataset configuration
- Added processing options to "Add New Dataset" form
- Added help text and cost/performance feedback
- Options are saved to and loaded from Cosmos DB

### Validation Results
- ✅ Backend deployed successfully
- ✅ Frontend deployed successfully
- ✅ Health checks passing
- ✅ API endpoints accessible
- 🔄 Manual UI testing required (see steps above)
- 🔄 End-to-end processing testing required

### Next Steps
1. Follow the manual testing steps above
2. Verify the UI shows processing options correctly
3. Test document processing with different option combinations
4. Validate that the backend respects the processing options
5. Check error handling and logging
