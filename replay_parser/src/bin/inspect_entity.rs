use anyhow::{Context as _, Result};
use source2_demo::prelude::*;
use std::collections::BTreeSet;
use std::env;
use std::fs;

struct EntityInspector {
    class_names: BTreeSet<String>,
    printed: BTreeSet<String>,
}

impl Default for EntityInspector {
    fn default() -> Self {
        Self {
            class_names: env::args().skip(2).collect(),
            printed: BTreeSet::new(),
        }
    }
}

#[observer]
impl EntityInspector {
    #[on_entity]
    fn on_entity(&mut self, event: EntityEvents, entity: &Entity) -> ObserverResult {
        let class_name = entity.class().name();
        if event != EntityEvents::Deleted && self.class_names.contains(class_name) && self.printed.insert(class_name.to_string())
        {
            println!("\n{class_name}\n");
            println!("{entity}");
        }

        Ok(())
    }

    #[on_stop]
    fn on_stop(&mut self, ctx: &Context) -> ObserverResult {
        for class_name in &self.class_names {
            if let Ok(entity) = ctx.entities().get_by_class_name(class_name) {
                println!("\n{class_name} (final)\n");
                println!("{entity}");
            }
        }

        Ok(())
    }
}

fn main() -> Result<()> {
    let path = env::args()
        .nth(1)
        .context("usage: inspect_entity <replay.dem> <class-name> [class-name ...]")?;
    if env::args().nth(2).is_none() {
        anyhow::bail!("missing class name");
    }
    let data = fs::read(&path).with_context(|| format!("unable to read {path}"))?;
    let mut parser = Parser::new(&data)?;

    parser.register_observer::<EntityInspector>();
    parser.run_to_end()?;

    Ok(())
}
