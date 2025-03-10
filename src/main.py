import os
from data_loaders import MedicalDataset, MissDataset, DataLoadersEnum
from itertools import product
from datetime import datetime
from tqdm import tqdm
from copy import deepcopy
import pickle
import json
import pandas as pd

from baseline_pipeline import BaselinePipeline
from feature_select_pipeline import FeatureSelectPipeline

import concurrent.futures

def save_model(model, filename):
    with open(filename, 'wb') as f:
        pickle.dump(model, f)

# Running experiment after setting up the parameters for one MISSING MECHANISM. Each missing mechanism is run separately
def run_custom_experiments(original_data, dataset_name, missing_param_dict, target_col, task_type='classification',n_folds=10):
    name='Experiment_' + str(datetime.now()),
    # Generate the list of all possible combinations of missing parameters
    missing_param_grid = list(product(*tuple(missing_param_dict.values())))
    print(f"\n-----------------------------   Experiment Missing Parameters  -----------------------------\n")
    # Print the total number of combinations
    print(f"Total length of experiment missing parameters: {len(missing_param_grid)}")

    # Print the actual combinations
    print("Experiment missing parameter grid:")

    for params in missing_param_grid:
        print(f"\t{params}")


    #############################
    ##IMPORTANT: Define the feature selection methods to be used
    fs_methods=[
                "information_gain",
                "correlation_coefficient",
                "chi_square",
                 "genetic_algorithm",
                 "RFE"]
    #############################



    param_lookup_dict = {}
    baseline_metrics_dfs = []
    baseline_imputation_eval_results = []

    # fs_metrics_dfs = []
    fs_metrics_type_dfs ={}
    # fs_imputation_eval_results = []
    fs_imputation_type_results = {}
    fs_selected_features_total = {}
    for fs in fs_methods:
        fs_metrics_type_dfs[fs] = []
        fs_imputation_type_results[fs] = []
        fs_selected_features_total[fs] = []

    miss_type = missing_param_dict['missing_mechanism']
    name = miss_type[0] + '_Experiment_' + str(datetime.now()).replace(':', '-').replace(' ', '_')

    with tqdm(total=len(missing_param_grid)) as pbar:
        for i, params in enumerate(missing_param_grid):
            print(f"\n-----------------------------  Starting experiments for {missing_param_dict['missing_mechanism']} {dataset_name}  -----------------------------\n")
            print(f"Starting experiment with params: {params}")
            original_data_copy = deepcopy(original_data)
            params = {k: p for k, p in zip(list(missing_param_dict.keys()), params)}
            param_lookup_dict[i] = params

             # Create MissDataset object
            dataset_object = MissDataset(
                data=original_data_copy,
                target_col=target_col,
                n_folds=n_folds,
                **params,
            )

            ##################
            baseline_metrics_dfs, baseline_imputation_eval_results,baseline_pipeline_experiment = baseline_experiment(
                dataset_object=dataset_object,
                dataset_name=dataset_name,
                params=params,
                name=name,
                i=i,
                baseline_metrics_dfs=baseline_metrics_dfs,
                baseline_imputation_eval_results=baseline_imputation_eval_results
            ) 


            for fs in fs_methods:
                fs_metrics_dfs, fs_imputation_eval_results, fs_pipeline_experiment, fs_selected_features = run_multiple_feature_selection(fs_metrics_type_dfs[fs],fs_imputation_type_results[fs],dataset_object,dataset_name,params,name,i, fs)
                fs_metrics_type_dfs[fs]=fs_metrics_dfs
                fs_imputation_type_results[fs]=fs_imputation_eval_results
                fs_selected_features_total[fs]=fs_selected_features
            
            ###################
            
            pbar.update(1)

    print("Combining and saving final results")
    ##############################
    save_baseline_experiment_results(
        baseline_metrics_dfs=baseline_metrics_dfs,
        baseline_imputation_eval_results=baseline_imputation_eval_results,
        baseline_pipeline_experiment=baseline_pipeline_experiment,
        param_lookup_dict=param_lookup_dict
    )
    for fs in fs_methods:
        single_fs_metrics_dfs=fs_metrics_type_dfs[fs]
        single_fs_imputation_eval_results=fs_imputation_type_results[fs]
        single_fs_feature_experiment=fs_selected_features_total[fs]
        save_feature_selection_experiment_results(
            fs_metrics_dfs=single_fs_metrics_dfs,
            fs_imputation_eval_results=single_fs_imputation_eval_results,
            fs_pipeline_experiment=fs_pipeline_experiment,
            param_lookup_dict=param_lookup_dict,
            feature_type=fs,
            fs_pipeline_features=single_fs_feature_experiment
            

        )
    ################################

def run_multiple_feature_selection(fs_metrics_dfs,fs_imputation_eval_results,dataset_object,dataset_name,params,name,i, fs):
    # fs_metrics_dfs = []
    # fs_imputation_eval_results = []
    fs_metrics_dfs, fs_imputation_eval_results, fs_pipeline_experiment, fs_selected_features = feature_selection_experiment(
                dataset_object=dataset_object,
                dataset_name=dataset_name,
                params=params,
                name=name,
                i=i,
                fs_metrics_dfs=fs_metrics_dfs,
                fs_imputation_eval_results=fs_imputation_eval_results,
                feature_type=fs

            )
    return fs_metrics_dfs, fs_imputation_eval_results, fs_pipeline_experiment, fs_selected_features


def baseline_experiment(dataset_object, dataset_name, params, name, i, baseline_metrics_dfs, baseline_imputation_eval_results):
    # Running Baseline Pipeline
    # NEW NEW
    baseline_pipeline_experiment = BaselinePipeline(
        dataset_object=dataset_object,
        dataset_name=dataset_name,
        missing_mechanism=params['missing_mechanism'],
        missing_percentage=params['p_miss'],    
        name=name
    )
    baseline_metrics_df, baseline_errors_df, baseline_preds_df, baseline_imputation_eval_df = baseline_pipeline_experiment.run()

    filename = 'combined-missing_param_' + str(i) + '.csv'
    
    # Saving errors
    errors_filename = os.path.join(baseline_pipeline_experiment.results_dir, 'errors_' + filename)
    baseline_errors_df.to_csv(errors_filename)
    
    # Saving metrics
    baseline_metrics_dfs.append(baseline_metrics_df)
    metrics_filename = os.path.join(baseline_pipeline_experiment.results_dir, 'prediction_metrics_' + filename)
    baseline_metrics_df.to_csv(metrics_filename)

    # Saving imputation evaluation results
    baseline_imputation_eval_results.append(baseline_imputation_eval_df)
    imputation_eval_filename = os.path.join(baseline_pipeline_experiment.results_dir, 'imputation_eval_' + filename)
    baseline_imputation_eval_df.to_csv(imputation_eval_filename)

    # Saving predictions
    preds_filename = os.path.join(baseline_pipeline_experiment.results_dir, 'predictions_' + filename)
    baseline_preds_df.to_csv(preds_filename)
    
    return baseline_metrics_dfs, baseline_imputation_eval_results, baseline_pipeline_experiment

def feature_selection_experiment(dataset_object, dataset_name, params, name, i, fs_metrics_dfs, fs_imputation_eval_results, feature_type):
    # Running Feature Selection Pipeline

    fs_pipeline_experiment = FeatureSelectPipeline(
        dataset_object=dataset_object,
        dataset_name=dataset_name,
        missing_mechanism=params['missing_mechanism'],
        missing_percentage=params['p_miss'],
        name=name,
        fs_type=feature_type
    )
    
    fs_metrics_df, fs_errors_df, fs_preds_df, fs_imputation_eval_df,fs_selected_features = fs_pipeline_experiment.run()

    filename = 'combined-missing_param_' + str(i) + '.csv'
    
    # Saving errors
    errors_filename = os.path.join(fs_pipeline_experiment.results_dir, feature_type +'_errors_' + filename)
    fs_errors_df.to_csv(errors_filename)
    
    # Saving metrics
    fs_metrics_dfs.append(fs_metrics_df)
    metrics_filename = os.path.join(fs_pipeline_experiment.results_dir, feature_type + '_prediction_metrics_' + filename)
    fs_metrics_df.to_csv(metrics_filename)

    # Saving imputation evaluation results
    fs_imputation_eval_results.append(fs_imputation_eval_df)
    imputation_eval_filename = os.path.join(fs_pipeline_experiment.results_dir, feature_type + '_imputation_eval_' + filename)
    fs_imputation_eval_df.to_csv(imputation_eval_filename)

    # Saving predictions
    preds_filename = os.path.join(fs_pipeline_experiment.results_dir, feature_type + '_predictions_' + filename)
    fs_preds_df.to_csv(preds_filename)

    # Saving selected features
    selected_features_df = pd.DataFrame(fs_selected_features)
    selected_features_filename = os.path.join(fs_pipeline_experiment.results_dir, feature_type + '_selected_features_' + filename)
    selected_features_df.to_csv(selected_features_filename)
    
    return fs_metrics_dfs, fs_imputation_eval_results, fs_pipeline_experiment,fs_selected_features

def save_baseline_experiment_results(baseline_metrics_dfs, baseline_imputation_eval_results, baseline_pipeline_experiment, param_lookup_dict):
    # Combining and saving final baseline results
    final_results = pd.concat(baseline_metrics_dfs)
    final_results.to_csv(os.path.join(baseline_pipeline_experiment.base_dir, 'prediction_metrics_final_results.csv'))

    combined_folds_imputation_eval_results_df = pd.concat(baseline_imputation_eval_results)
    combined_folds_imputation_eval_results_df.to_csv(os.path.join(baseline_pipeline_experiment.base_dir, 'imputation_eval_final_results.csv'))

    param_lookup_dict_json = json.dumps(param_lookup_dict)
    with open(os.path.join(baseline_pipeline_experiment.base_dir, 'params_lookup.json'), 'w') as f:
        f.write(param_lookup_dict_json)

    print(baseline_pipeline_experiment.base_dir)

def save_feature_selection_experiment_results(fs_metrics_dfs, fs_imputation_eval_results, fs_pipeline_experiment, param_lookup_dict, feature_type,fs_pipeline_features):
    # Combining and saving final feature selection results
    final_results = pd.concat(fs_metrics_dfs)
    final_results.to_csv(os.path.join(fs_pipeline_experiment.base_dir,feature_type +'_prediction_metrics_final_results.csv'))

    combined_folds_imputation_eval_results_df = pd.concat(fs_imputation_eval_results)
    combined_folds_imputation_eval_results_df.to_csv(os.path.join(fs_pipeline_experiment.base_dir,feature_type +'_imputation_eval_final_results.csv'))

    param_lookup_dict_json = json.dumps(param_lookup_dict)
    with open(os.path.join(fs_pipeline_experiment.base_dir, 'params_lookup.json'), 'w') as f:
        f.write(param_lookup_dict_json)

    features_df = pd.DataFrame(fs_pipeline_features)
    features_df.to_csv(os.path.join(fs_pipeline_experiment.base_dir, feature_type + '_selected_features.csv'), index=False)


    



CURRENT_SUPPORTED_DATALOADERS = {
    # # 'eeg_eye_state': DataLoadersEnum.prepare_eeg_eye_data,
    'Cleveland Heart Disease': DataLoadersEnum.prepare_cleveland_heart_data,
    # 'diabetic_retinopathy': DataLoadersEnum.prepare_diabetic_retinopathy_dataset,
    # 'wdbc': DataLoadersEnum.prepare_wdbc_data
   
}

# Setting up experiment parameters
def run(custom_experiment_data_object, task_type='classification'):
    MCAR_PARAM_DICT = {
        # 'p_miss': [x/10 for x in range(3,9)], 
        'p_miss': [0.1, 0.2, 0.3, 0.4, 0.5],
        'missing_mechanism': ["MCAR"],
        'opt': [None],
        'p_obs': [None],
        'q': [None],
    }

    MAR_PARAM_DICT = {
        # 'p_miss': [x/10 for x in range(3,9)], 
        # 0.1, 0.2, 0.3,
        'p_miss': [0.1, 0.2, 0.3, 0.4, 0.5],
        'missing_mechanism': ["MAR"],
        'opt': [None],
        'p_obs': [0.3],
        'q': [None],
    }

    MNAR_PARAM_DICT = {
        'p_miss': [0.1, 0.2, 0.3, 0.4, 0.5],
        'missing_mechanism': ["MNAR"],
        'opt': ['logistic'],
        'p_obs': [0.3],
        'q': [None],
    }

    for d in [MAR_PARAM_DICT,MCAR_PARAM_DICT,MNAR_PARAM_DICT]:
        run_custom_experiments(
            original_data=custom_experiment_data_object.data,
            dataset_name=custom_experiment_data_object.dataset_name,
            missing_param_dict=d,
            target_col=custom_experiment_data_object.target_col,
            task_type=task_type,
            n_folds=10
        )




# Driver Function
# def main():
    
#     total_trials = 5
#     for i in range(0, total_trials):
#         for dataset_name, data_preparation_function_object in CURRENT_SUPPORTED_DATALOADERS.items():
#             print(f"\nTrial: {i+1}/{total_trials} for Dataset: {dataset_name}")
#             run(data_preparation_function_object(), task_type='classification')



############################################


def main():
    total_trials = 10
    tasks = []

    # Collect all tasks to run in parallel
    for i in range(total_trials):
        for dataset_name, data_preparation_function_object in CURRENT_SUPPORTED_DATALOADERS.items():
            print(f"\nPreparing Task: Trial: {i+1}/{total_trials} for Dataset: {dataset_name}")
            tasks.append((i, dataset_name, data_preparation_function_object))

    # Run all tasks in parallel using ProcessPoolExecutor
    with concurrent.futures.ProcessPoolExecutor(max_workers=5) as executor:
        futures = [
            executor.submit(run_task, trial, dataset_name, data_preparation_function_object)
            for trial, dataset_name, data_preparation_function_object in tasks
        ]

        # Collect results (if necessary)
        for future in concurrent.futures.as_completed(futures):
            try:
                future.result()  # Handle any raised exceptions
            except Exception as exc:
                print(f"Task generated an exception: {exc}")

def run_task(trial, dataset_name, data_preparation_function_object):
    print(f"Running Trial: {trial+1} for Dataset: {dataset_name}")
    run(data_preparation_function_object(), task_type='classification')


############################################

if __name__ == '__main__':
    
    main()