claudia-container API reference
===============================

.. module:: claudia_container

The public API is exactly what ``claudia_container.__all__`` lists (see :doc:`../versioning`). The design behind it
(decisions D70 to D82) is in the project document ``e2-container-design.md``.

Passwords
---------

.. autodata:: claudia_container.MIN_PASSWORD_LENGTH
.. autoexception:: claudia_container.WeakPassword
.. autofunction:: claudia_container.password_problems
.. autofunction:: claudia_container.require_strong_password

Cryptographic primitives
------------------------

.. autoclass:: claudia_container.KdfParams
   :members:
.. autoclass:: claudia_container.LoginMaterial
.. autofunction:: claudia_container.derive_login_material
.. autofunction:: claudia_container.warm_login_material
.. autofunction:: claudia_container.calibrate
.. autofunction:: claudia_container.derive_recovery_material
.. autofunction:: claudia_container.random_key
.. autofunction:: claudia_container.seal
.. autofunction:: claudia_container.open_sealed
.. autoexception:: claudia_container.DecryptionError

Key slots
---------

.. autoclass:: claudia_container.Role
   :members:
   :undoc-members:
.. autoclass:: claudia_container.Domain
   :members:
   :undoc-members:
.. autodata:: claudia_container.ROLE_DOMAINS
.. autoclass:: claudia_container.KeySlot
   :members:
.. autoclass:: claudia_container.Unlocked
.. autofunction:: claudia_container.new_domain_keys
.. autofunction:: claudia_container.make_slot
.. autofunction:: claudia_container.open_slot

Recovery key
------------

.. autofunction:: claudia_container.new_recovery_key
.. autofunction:: claudia_container.format_recovery_key
.. autofunction:: claudia_container.parse_recovery_key
.. autoexception:: claudia_container.InvalidRecoveryKey

The document file
-----------------

A document is a zip file with a readable manifest, the key slots, the sealed list of its people and, once packed, the
history and chat as blocks. Every change replaces the file atomically.

.. autofunction:: claudia_container.create_document
.. autofunction:: claudia_container.clean_details
.. autofunction:: claudia_container.read_manifest
.. autofunction:: claudia_container.unlock
.. autofunction:: claudia_container.unlock_with_recovery
.. autofunction:: claudia_container.warm
.. autofunction:: claudia_container.read_people
.. autofunction:: claudia_container.add_user
.. autofunction:: claudia_container.remove_user
.. autofunction:: claudia_container.change_password
.. autoclass:: claudia_container.Manifest
   :members:
.. autoclass:: claudia_container.Person
.. autoexception:: claudia_container.ContainerError
.. autoexception:: claudia_container.NotAClaudiaDocument
.. autoexception:: claudia_container.UnsupportedFormat
.. autoexception:: claudia_container.OutdatedFormat
.. autoexception:: claudia_container.ReaderLimitExceeded
.. autoexception:: claudia_container.TamperedDocument

Keys of people, renewal and the private domain
----------------------------------------------

Every person has a key pair; keys she is not there to receive wait in a sealed inbox until her next login (D1274).
Removing a person or lowering an editor renews the keys she held (D1263), in one atomic replacement of the file. The private
domain of a person is a chain only her own key opens (D1265).

.. autoclass:: claudia_container.KeyPair
.. autofunction:: claudia_container.new_key_pair
.. autofunction:: claudia_container.seal_to
.. autofunction:: claudia_container.open_inbox
.. autofunction:: claudia_container.change_role
.. autofunction:: claudia_container.remove_person
.. autoclass:: claudia_container.Renewed
.. autoexception:: claudia_container.RenewalInterrupted
.. autoclass:: claudia_container.PrivateDomain
.. autofunction:: claudia_container.new_private_domain
.. autofunction:: claudia_container.read_private
.. autofunction:: claudia_container.write_private

The recovery key of a document
------------------------------

.. autofunction:: claudia_container.has_recovery_key
.. autofunction:: claudia_container.set_recovery_key
.. autofunction:: claudia_container.recover_access

The journal
-----------

Every change of an open document is appended to a sealed journal before it is acknowledged.

.. autoclass:: claudia_container.JournalWriter
   :members:
.. autofunction:: claudia_container.read_journal
.. autofunction:: claudia_container.journal_generation
.. autoclass:: claudia_container.JournalRecord
.. autoexception:: claudia_container.JournalError

Blocks, head and snapshot
-------------------------

Packing folds the journal into blocks (a hash chain per domain), writes the head record and a snapshot, and replaces the
file first and the journal second.

.. autofunction:: claudia_container.read_state
.. autofunction:: claudia_container.begin
.. autofunction:: claudia_container.pack_journal
.. autofunction:: claudia_container.read_snapshot
.. autoclass:: claudia_container.State
.. automodule:: claudia_container.blocks
   :members: seal_block, open_block, seal_head, open_head, Head, Chain, Place, BlockError, block_hash

What leaves the document
------------------------

Every export, print and PDF is written to an audit chain sealed with the history key (D1271), and an export can be
written as a plain zip that Claudia reads back (D1270, D1272).

.. autoclass:: claudia_container.AuditRecord
   :members:
.. autofunction:: claudia_container.read_audit
.. autofunction:: claudia_container.record_audit
.. autofunction:: claudia_container.write_export
.. autofunction:: claudia_container.read_export
.. autofunction:: claudia_container.is_export
.. autoclass:: claudia_container.ExportFile
.. autoexception:: claudia_container.ExportRefused
