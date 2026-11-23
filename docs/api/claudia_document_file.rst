claudia-document-file API reference
===================================

.. module:: claudia_document_file

The public API is exactly what ``claudia_document_file.__all__`` lists (see :doc:`../versioning`). The design behind it
(decisions D70 to D82) is in the project document ``e2-container-design.md``.

Passwords
---------

.. autodata:: claudia_document_file.MIN_PASSWORD_LENGTH
.. autoexception:: claudia_document_file.WeakPassword
.. autofunction:: claudia_document_file.password_problems
.. autofunction:: claudia_document_file.require_strong_password

Cryptographic primitives
------------------------

.. autoclass:: claudia_document_file.KdfParams
   :members:
.. autoclass:: claudia_document_file.LoginMaterial
.. autofunction:: claudia_document_file.derive_login_material
.. autofunction:: claudia_document_file.warm_login_material
.. autofunction:: claudia_document_file.calibrate
.. autofunction:: claudia_document_file.derive_recovery_material
.. autofunction:: claudia_document_file.random_key
.. autofunction:: claudia_document_file.seal
.. autofunction:: claudia_document_file.open_sealed
.. autoexception:: claudia_document_file.DecryptionError

Key slots
---------

.. autoclass:: claudia_document_file.Role
   :members:
   :undoc-members:
.. autoclass:: claudia_document_file.Part
   :members:
   :undoc-members:
.. autodata:: claudia_document_file.ROLE_PARTS
.. autoclass:: claudia_document_file.KeySlot
   :members:
.. autoclass:: claudia_document_file.Unlocked
.. autofunction:: claudia_document_file.new_part_keys
.. autofunction:: claudia_document_file.make_slot
.. autofunction:: claudia_document_file.open_slot

Recovery key
------------

.. autofunction:: claudia_document_file.new_recovery_key
.. autofunction:: claudia_document_file.format_recovery_key
.. autofunction:: claudia_document_file.parse_recovery_key
.. autoexception:: claudia_document_file.InvalidRecoveryKey

The document file
-----------------

A document is a zip file with a readable manifest, the key slots, the sealed list of its people and, once packed, the
history and chat as blocks. Every change replaces the file atomically.

.. autofunction:: claudia_document_file.create_document
.. autofunction:: claudia_document_file.clean_details
.. autofunction:: claudia_document_file.read_manifest
.. autofunction:: claudia_document_file.unlock
.. autofunction:: claudia_document_file.unlock_with_recovery
.. autofunction:: claudia_document_file.warm
.. autofunction:: claudia_document_file.read_people
.. autofunction:: claudia_document_file.add_user
.. autofunction:: claudia_document_file.remove_user
.. autofunction:: claudia_document_file.change_password
.. autoclass:: claudia_document_file.Manifest
   :members:
.. autoclass:: claudia_document_file.Person
.. autoexception:: claudia_document_file.DocumentFileError
.. autoexception:: claudia_document_file.NotAClaudiaDocument
.. autoexception:: claudia_document_file.UnsupportedFormat
.. autoexception:: claudia_document_file.OutdatedFormat
.. autoexception:: claudia_document_file.ReaderLimitExceeded
.. autoexception:: claudia_document_file.TamperedDocument

Keys of people, renewal and private notes
-----------------------------------------

Every person has a key pair; keys she is not there to receive wait in a sealed inbox until her next login (D1274).
Removing a person or lowering an editor renews the keys she held (D1263), in one atomic replacement of the file. A person's private
notes are a chain only her own key opens (D1265).

.. autoclass:: claudia_document_file.KeyPair
.. autofunction:: claudia_document_file.new_key_pair
.. autofunction:: claudia_document_file.seal_to
.. autofunction:: claudia_document_file.open_inbox
.. autofunction:: claudia_document_file.change_role
.. autofunction:: claudia_document_file.remove_person
.. autoclass:: claudia_document_file.Renewed
.. autoexception:: claudia_document_file.RenewalInterrupted
.. autoclass:: claudia_document_file.PrivateNotesKey
.. autofunction:: claudia_document_file.new_private_notes_key
.. autofunction:: claudia_document_file.read_private
.. autofunction:: claudia_document_file.write_private

The recovery key of a document
------------------------------

.. autofunction:: claudia_document_file.has_recovery_key
.. autofunction:: claudia_document_file.set_recovery_key
.. autofunction:: claudia_document_file.recover_access

The journal
-----------

Every change of an open document is appended to a sealed journal before it is acknowledged.

.. autoclass:: claudia_document_file.JournalWriter
   :members:
.. autofunction:: claudia_document_file.read_journal
.. autofunction:: claudia_document_file.journal_generation
.. autoclass:: claudia_document_file.JournalRecord
.. autoexception:: claudia_document_file.JournalError

Blocks, head and snapshot
-------------------------

Packing folds the journal into blocks (a hash chain per stream), writes the head record and a snapshot, and replaces the
file first and the journal second.

.. autofunction:: claudia_document_file.read_state
.. autofunction:: claudia_document_file.begin
.. autofunction:: claudia_document_file.pack_journal
.. autofunction:: claudia_document_file.read_snapshot
.. autoclass:: claudia_document_file.State
.. automodule:: claudia_document_file.blocks
   :members: seal_block, open_block, seal_head, open_head, Head, Chain, Place, BlockError, block_hash

What leaves the document
------------------------

Every export, print and PDF is written to an audit chain sealed with the history key (D1271), and an export can be
written as a plain zip that Claudia reads back (D1270, D1272).

.. autoclass:: claudia_document_file.AuditRecord
   :members:
.. autoclass:: claudia_document_file.ConsentRecord
.. autofunction:: claudia_document_file.read_audit
.. autofunction:: claudia_document_file.record_audit
.. autofunction:: claudia_document_file.write_export
.. autofunction:: claudia_document_file.read_export
.. autofunction:: claudia_document_file.is_export
.. autoclass:: claudia_document_file.ExportFile
.. autoexception:: claudia_document_file.ExportRefused
