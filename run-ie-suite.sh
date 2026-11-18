# run our own lib

# run our own test suite

uv run python scripts/run_test_documents.py  
cp test-documents/catalogue.json /home/m/Dev/claudia/test-results/claudia-tests.json


# run on libreoffice test docs

uv run python scripts/run_test_documents.py \
  --corpus /home/m/Dev/claudia/test-corpus/libreoffice/sw/qa/extras/ooxmlimport/data \
  --corpus-report /home/m/Dev/claudia/test-results/ooxmlimport.json
  
# run on apache poi

uv run python scripts/run_test_documents.py \
  --corpus /home/m/Dev/claudia/test-corpus/poi-docs/test-data/document \
  --corpus-report /home/m/Dev/claudia/test-results/poi-docs.json


# uv run python scripts/run_test_documents.py --corpus <folder> | grep -v '^PASS\|rewritten parts'
