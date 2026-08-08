"""Train/serve parity tests.

The insurance policy of the whole project: the same events pushed through the
offline replay path and the online (materialised-profile) path must produce
identical feature vectors. Filled in during Step 4/Phase 3.
"""

import pytest


@pytest.mark.skip(reason="Features not implemented yet (Phase 1, Step 4).")
def test_offline_online_parity():
    raise NotImplementedError
