# Everything runs through Docker (scripts/run.sh); nothing is installed on the host.
.PHONY: package test chat-env-test clean
package:            ## build dist/rule-check.zip (explicit include list, no tests)
	./scripts/run.sh python3 /skill/scripts/package.py /work/dist/rule-check.zip
test:               ## both scenarios in the regular image
	cd tests && ../scripts/run.sh python3 /skill/tests/score.py run && ../scripts/run.sh python3 /skill/tests/score_v2.py run2
chat-env-test:      ## old + new chat-environment images, both engines, classified comparison
	bash tests/chat_env_test.sh
clean:
	rm -rf dist tests/_out tests/_o_* tests/_base
