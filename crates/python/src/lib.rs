mod output;

use pyo3::prelude::*;
use std::any::Any;

pub use output::{Output, Replay, ReplayMetadata, ReplayPlayer, VisionSample};

#[global_allocator]
static ALLOCATOR: mimalloc::MiMalloc = mimalloc::MiMalloc;

#[pyfunction]
pub fn parse_replay(data: &[u8]) -> PyResult<Replay> {
    catch_parser_error("replay", || wardmap_parser::parse_replay(data)).map(Replay::from)
}

#[pyfunction]
pub fn parse_vision(data: &[u8]) -> PyResult<Vec<VisionSample>> {
    catch_parser_error("vision", || wardmap_parser::parse_vision(data))
        .map(|rows| rows.into_iter().map(VisionSample::from).collect())
}

fn catch_parser_error<T>(operation: &str, parse: impl FnOnce() -> anyhow::Result<T> + std::panic::UnwindSafe) -> PyResult<T> {
    std::panic::catch_unwind(parse)
        .map_err(|payload| {
            parser_exception(format!(
                "Panic while parsing {operation}: {}",
                panic_message(payload.as_ref())
            ))
        })?
        .map_err(|error| parser_exception(format!("Error while parsing {operation}\n{error}")))
}

fn parser_exception(message: String) -> PyErr {
    PyErr::new::<pyo3::exceptions::PyException, _>(message)
}

fn panic_message(payload: &(dyn Any + Send)) -> String {
    if let Some(message) = payload.downcast_ref::<String>() {
        message.clone()
    } else if let Some(message) = payload.downcast_ref::<&str>() {
        (*message).to_string()
    } else {
        "non-string panic payload".to_string()
    }
}

#[pymodule]
#[pyo3(name = "d2wm_parser")]
fn d2wm_parser(module: &Bound<'_, PyModule>) -> PyResult<()> {
    module.add_class::<Replay>()?;
    module.add_class::<ReplayMetadata>()?;
    module.add_class::<ReplayPlayer>()?;
    module.add_class::<Output>()?;
    module.add_class::<VisionSample>()?;
    module.add_function(wrap_pyfunction!(parse_replay, module)?)?;
    module.add_function(wrap_pyfunction!(parse_vision, module)?)
}
