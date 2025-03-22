#!/usr/bin/env python3
"""
FEWS Network Visualization - Dead Points Analyzer

This script identifies "dead points" in a FEWS configuration - time series sets that are 
neither used as inputs for any transformation nor marked as endpoints. These dead points 
may represent configuration issues, orphaned data, or unnecessary elements that could be 
cleaned up.
"""

import os
import sqlite3
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path
import argparse
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('dead_points_analyzer')

def connect_to_db(db_path):
    """Connect to the SQLite database."""
    if not os.path.exists(db_path):
        raise FileNotFoundError(f"Database file not found: {db_path}")
    
    logger.info(f"Connecting to database: {db_path}")
    return sqlite3.connect(db_path)

def find_dead_points(conn):
    """Find time series sets that are neither used as inputs nor endpoints."""
    query = """
    SELECT ts.id, ts.modins, ts.parid, ts.qualifiers, ts.tstype, ts.timess
    FROM ts_sets ts
    WHERE ts.id NOT IN (
        -- TSS used as inputs for transformations
        SELECT DISTINCT tss_id 
        FROM links 
        WHERE inout = 'in'
    )
    AND ts.id NOT IN (
        -- TSS marked as endpoints
        SELECT tss_id 
        FROM endpoints
    )
    ORDER BY ts.modins, ts.parid
    """
    
    logger.info("Executing dead points query")
    return pd.read_sql_query(query, conn)

def find_producing_transformations(conn, tss_ids):
    """Find transformations that produce these dead point time series sets."""
    if not tss_ids:
        return pd.DataFrame()
    
    placeholders = ','.join('?' for _ in tss_ids)
    query = f"""
    SELECT l.tss_id, t.id AS trafo_id, t.desc AS trafo_desc, 
           m.modins AS module_instance, c.wf_id AS workflow_id
    FROM links l
    JOIN trafos t ON l.trafo_id = t.id
    JOIN modins_calls m ON t.mic_id = m.id
    JOIN call_stacks c ON m.call_stack_id = c.id
    WHERE l.tss_id IN ({placeholders})
    AND l.inout = 'out'
    ORDER BY l.tss_id
    """
    
    logger.info(f"Finding transformations that produce {len(tss_ids)} dead points")
    return pd.read_sql_query(query, conn, params=tss_ids)

def analyze_dead_points_by_module(dead_points_df):
    """Analyze dead points distribution by module instance."""
    if dead_points_df.empty:
        logger.info("No dead points found to analyze")
        return None
    
    logger.info("Analyzing dead points by module instance")
    return dead_points_df.groupby('modins').size().reset_index(name='count').sort_values('count', ascending=False)

def visualize_dead_points(module_counts, output_path=None):
    """Create a bar chart visualization of dead points by module instance."""
    if module_counts is None or module_counts.empty:
        logger.warning("No data available for visualization")
        return
    
    plt.figure(figsize=(12, 8))
    sns.set_style("whitegrid")
    
    # Create bar chart
    ax = sns.barplot(x='count', y='modins', data=module_counts)
    
    # Add labels and title
    plt.title('Dead Points by Module Instance', fontsize=16)
    plt.xlabel('Number of Dead Points', fontsize=12)
    plt.ylabel('Module Instance', fontsize=12)
    
    # Add count labels to the bars
    for i, v in enumerate(module_counts['count']):
        ax.text(v + 0.1, i, str(v), va='center')
    
    plt.tight_layout()
    
    # Save or display the figure
    if output_path:
        plt.savefig(output_path)
        logger.info(f"Visualization saved to {output_path}")
    else:
        plt.show()

def export_to_csv(df, output_path):
    """Export a DataFrame to CSV."""
    if df.empty:
        logger.warning("No data to export")
        return
    
    df.to_csv(output_path, index=False)
    logger.info(f"Data exported to {output_path}")

def generate_report(dead_points_df, producing_trafos_df, output_dir):
    """Generate a comprehensive report on dead points."""
    if dead_points_df.empty:
        logger.info("No dead points found to report on")
        return
    
    # Ensure output directory exists
    os.makedirs(output_dir, exist_ok=True)
    
    # Create report file
    report_path = os.path.join(output_dir, "dead_points_report.txt")
    
    with open(report_path, 'w') as f:
        f.write("FEWS Configuration Dead Points Analysis Report\n")
        f.write("=" * 50 + "\n\n")
        
        # Summary statistics
        f.write("Summary:\n")
        f.write("-" * 50 + "\n")
        f.write(f"Total dead points found: {len(dead_points_df)}\n")
        f.write(f"Modules with dead points: {dead_points_df['modins'].nunique()}\n")
        f.write(f"Parameters affected: {dead_points_df['parid'].nunique()}\n\n")
        
        # Dead points by module
        module_counts = analyze_dead_points_by_module(dead_points_df)
        f.write("Dead Points by Module:\n")
        f.write("-" * 50 + "\n")
        for _, row in module_counts.iterrows():
            f.write(f"{row['modins']}: {row['count']} dead points\n")
        f.write("\n")
        
        # Sample of dead points
        f.write("Sample of Dead Points:\n")
        f.write("-" * 50 + "\n")
        sample = dead_points_df.head(20)  # Show up to 20 examples
        for _, row in sample.iterrows():
            f.write(f"ID: {row['id']}, Module: {row['modins']}, Parameter: {row['parid']}")
            if row['qualifiers']:
                f.write(f", Qualifiers: {row['qualifiers']}")
            f.write("\n")
        
        if len(dead_points_df) > 20:
            f.write(f"... and {len(dead_points_df) - 20} more\n")
        f.write("\n")
        
        # Information about producing transformations
        f.write("Producing Transformations:\n")
        f.write("-" * 50 + "\n")
        if producing_trafos_df.empty:
            f.write("No information about producing transformations found.\n")
        else:
            trafos_by_tss = producing_trafos_df.groupby('tss_id')
            sample_tss_ids = dead_points_df['id'].head(10).tolist()
            
            for tss_id in sample_tss_ids:
                if tss_id in trafos_by_tss.groups:
                    tss_info = dead_points_df[dead_points_df['id'] == tss_id].iloc[0]
                    f.write(f"Time Series ID {tss_id} ({tss_info['modins']}/{tss_info['parid']}):\n")
                    
                    for _, trafo in trafos_by_tss.get_group(tss_id).iterrows():
                        f.write(f"  - Produced by: {trafo['trafo_desc']} ")
                        f.write(f"(Transformation ID: {trafo['trafo_id']}, ")
                        f.write(f"Module: {trafo['module_instance']}, ")
                        f.write(f"Workflow: {trafo['workflow_id']})\n")
                    f.write("\n")
        
        # Recommendations
        f.write("Recommendations:\n")
        f.write("-" * 50 + "\n")
        f.write("1. Review the identified dead points to determine if they are needed\n")
        f.write("2. Consider removing unused time series sets to simplify configuration\n")
        f.write("3. Check if any dead points should be marked as endpoints\n")
        f.write("4. Verify if transformations producing these time series are working as expected\n")
    
    logger.info(f"Report generated at {report_path}")
    return report_path

def main():
    """Main function to analyze dead points in FEWS configuration."""
    parser = argparse.ArgumentParser(description='Analyze dead points in FEWS configuration')
    parser.add_argument('--db', type=str, default='../db/fews_config.db3',
                      help='Path to the SQLite database file')
    parser.add_argument('--output-dir', type=str, default='./output',
                      help='Directory to save output files')
    parser.add_argument('--csv', action='store_true',
                      help='Export results to CSV')
    parser.add_argument('--visualize', action='store_true',
                      help='Generate visualizations')
    args = parser.parse_args()
    
    # Create output directory if it doesn't exist
    os.makedirs(args.output_dir, exist_ok=True)
    
    try:
        # Connect to the database
        conn = connect_to_db(args.db)
        
        # Find dead points
        dead_points_df = find_dead_points(conn)
        
        if dead_points_df.empty:
            logger.info("No dead points found in the configuration")
            return
        
        logger.info(f"Found {len(dead_points_df)} dead points")
        
        # Find transformations that produce these dead points
        producing_trafos_df = find_producing_transformations(conn, dead_points_df['id'].tolist())
        
        # Analyze dead points by module
        module_counts = analyze_dead_points_by_module(dead_points_df)
        
        # Export to CSV if requested
        if args.csv:
            csv_path = os.path.join(args.output_dir, "dead_points.csv")
            export_to_csv(dead_points_df, csv_path)
            
            if not producing_trafos_df.empty:
                producers_csv_path = os.path.join(args.output_dir, "dead_points_producers.csv")
                export_to_csv(producing_trafos_df, producers_csv_path)
        
        # Generate visualizations if requested
        if args.visualize and module_counts is not None:
            viz_path = os.path.join(args.output_dir, "dead_points_by_module.png")
            visualize_dead_points(module_counts, viz_path)
        
        # Generate a comprehensive report
        generate_report(dead_points_df, producing_trafos_df, args.output_dir)
        
        # Close the connection
        conn.close()
        
        logger.info("Analysis complete")
        
    except Exception as e:
        logger.error(f"Error during analysis: {e}", exc_info=True)
        return 1
    
    return 0

if __name__ == "__main__":
    exit(main()) 