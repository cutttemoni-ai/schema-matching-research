from hashlib import sha256
import pytest
from scripts.verify_final_study_v2 import verify_files,validate_guest


def test_data_guard_rejects_modified_truth_or_input_before_model_submission(tmp_path):
    path=tmp_path/'raw.csv';path.write_bytes(b'original')
    expected={'raw.csv':sha256(b'original').hexdigest()}
    verify_files(expected,tmp_path)
    path.write_bytes(b'changed')
    with pytest.raises(ValueError):verify_files(expected,tmp_path)


def test_resume_guest_guard_rejects_other_weights_or_unfinished_work():
    value={'active':None,'ollama_version':'fixed','model_digest':'expected'}
    assert validate_guest(value,'expected','fixed')
    with pytest.raises(ValueError):validate_guest(value|{'model_digest':'new'},'expected','fixed')
    with pytest.raises(ValueError):validate_guest(value|{'active':{'request_id':'unknown'}},'expected','fixed')
