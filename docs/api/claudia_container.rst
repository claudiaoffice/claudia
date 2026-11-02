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
