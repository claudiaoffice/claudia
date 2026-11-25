"""What a document needs from the server it is opened on (E1.9, D1306, D1313): bound so that its scenarios are counted.

Every scenario is ``@pending:e1.9`` or waits for the owner's decision, and E1.9 is still being built elsewhere: none
has step code yet, so each is reported as skipped ("not automated yet") instead of running nowhere (PROC-40). The step
code comes with E1.9.
"""

from pytest_bdd import scenarios

scenarios("../../../claudiaoffice-log/specs/document-file/requirements.feature")
