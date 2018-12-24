
local: clean projects
	sphinx-build _source _build -t local

web: clean projects
	sphinx-build _source _build -t web
	# Some sources may contain sensitive information
	rm -rf _build/_sources/

projects:
	python _source/projects/load_projects.py

clean:
	rm -rf _build
	rm _source/projects/*.rst
