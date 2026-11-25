# Development tasks. Everything runs inside Docker via dev/run.sh; nothing is installed on the host.
# (Using the skill itself needs only Python 3, see SKILL.md.)
.PHONY: package test chat-env-test clean
package:            ## build dist/rule-check.zip (explicit include list; no tests, no dev tooling)
	./dev/run.sh python3 /skill/dev/package.py /work/dist/rule-check.zip
test:               ## both scenarios end to end in the regular image (self-contained, works on a fresh clone)
	mkdir -p tests/_out_test
	./dev/run.sh bash /skill/tests/run_deterministic.sh /work/tests/_out_test > tests/_out_test.log 2>&1 || { cat tests/_out_test.log; exit 1; }
	bash tests/assert_clean.sh tests/_out_test.log
chat-env-test:      ## old + new chat-environment images, both engines, classified comparison
	bash tests/chat_env_test.sh
clean:
	rm -rf dist tests/_out tests/_out_test tests/_out_test.log
