#include <Python.h>
#include "BKE_undo_system.h" // Blender's undo system API
#include "BLI_listbase.h"    // Blender's list handling
#include "MEM_guardedalloc.h"

// Function to get undo stack information
static PyObject* get_undo_steps(PyObject* self, PyObject* args) {
    UndoStack* undoStack = BKE_undosys_stack_get();
    if (!undoStack) {
        PyErr_SetString(PyExc_RuntimeError, "Failed to get undo stack");
        return NULL;
    }

    PyObject* undoList = PyList_New(0); // Create a Python list to store undo steps

    LISTBASE_FOREACH (UndoStep*, step, &undoStack->steps) {
        PyObject* stepInfo = Py_BuildValue(
            "{s:s, s:i}",
            "name", step->name ? step->name : "(unnamed)",
            "type", step->type
        );
        PyList_Append(undoList, stepInfo);
        Py_DECREF(stepInfo);
    }

    return undoList;
}

// Method definition table
static PyMethodDef moduleMethods[] = {
    {"get_undo_steps", get_undo_steps, METH_NOARGS, "Get the undo steps"},
    {NULL, NULL, 0, NULL}
};

// Module definition
static struct PyModuleDef moduleDef = {
    PyModuleDef_HEAD_INIT,
    "amagatex", // Module name
    NULL,         // Module documentation
    -1,           // Size of per-interpreter state of the module
    moduleMethods
};

// Module initialization
PyMODINIT_FUNC PyInit_amagatex(void) {
    return PyModule_Create(&moduleDef);
}
