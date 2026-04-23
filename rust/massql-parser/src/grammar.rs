use pest_derive::Parser;

#[derive(Parser)]
#[grammar = "msql.pest"]
pub struct MsqlParser;
