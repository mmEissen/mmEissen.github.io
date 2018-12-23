
local: clean
	sphinx-build _source _build -t local
web: clean
	sphinx-build _source _build -t web
	# Some sources may contain sensitive information
	rm -rf _build/_sources/
clean:
	rm -rf _build
