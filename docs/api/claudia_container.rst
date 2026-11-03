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
.. autofunction:: claudia_container.read_manifest
.. autofunction:: claudia_container.unlock
.. autofunction:: claudia_container.unlock_with_recovery
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
.. autoexception:: claudia_container.ReaderLimitExceeded
.. autoexception:: claudia_container.TamperedDocument

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
