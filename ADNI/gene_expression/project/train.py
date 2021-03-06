#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Thu Jan  7 14:37:28 2021
This script trains classifiers over ADNI blood gene expression features, 
Computes feature importance and saves SHAP plots for them

It makes use of Xin's code in 
https://github.com/linbrainlab/machinelearning.git

@author: subashkhanal
"""

from config import cfg, HyperParameters
import pandas as pd
import numpy as np
from sklearn.metrics import roc_curve, auc
from sklearn.model_selection import StratifiedKFold
from sklearn.utils import shuffle
from sklearn.preprocessing import label_binarize
from sklearn.metrics import f1_score
from sklearn.preprocessing import StandardScaler
from classifiers import classifier
from utilities import plot_SHAP, plot_ROC, save_results
import os
import itertools

def train_ADNI(features,clf,estimators,classes,repeat,data_path,results_path,plots_path):
    df_gene_dx = pd.read_csv(os.path.join(data_path, classes+'_filtered.csv')) #Remove _filtered to run experiments for un-preprocessed data
    ttest_df = pd.read_csv(cfg.filtered_ttest) #Use cfg.ttest for Un-preprocessed experiment
    important_probes =  ttest_df.sort_values(classes)['Genes'][0:features]
    df = df_gene_dx.loc[:,important_probes] # until we decide on which column to choose
    cols = df.columns
    df['DX'] = df_gene_dx['DX']
#Counter({'CN': 244, 'Dementia': 113, 'MCI': 377, nan: 10}) #labels distribution (Unfiltered based on RIN)
#{'CN': 118, 'Dementia': 56, 'MCI': 196, nan: 6}) #filtered based on  RIN
    df_CN = df[df.DX=='CN'] 
    df_MCI = df[df.DX=='MCI']
    df_AD= df[df.DX=='Dementia']
    
    #possible_classes = ['CN_MCI','CN_AD','MCI_AD']
    if classes == 'CN_MCI':
        df1 = df_CN
        df2 = df_MCI
        label1 = 'CN'
        label2 = 'MCI'
        
    if classes == 'CN_AD':
        df1 = df_CN
        df2 = df_AD
        label1 = 'CN'
        label2 = 'Dementia'
        
    if classes == 'MCI_AD':
        df1 = df_MCI
        df2 = df_AD
        label1 = 'MCI'
        label2 = 'Dementia'
        
    df_sampled = pd.concat([df1, df2])
    df_sampled = shuffle(df_sampled, random_state = 42)
    y = df_sampled.DX
    X = df_sampled.drop('DX',axis=1)
    
    y = label_binarize(y, classes=[label1, label2])
    
    numFeature=X.shape[1]
    y=y.ravel()
   
    scaler = StandardScaler()
    scaler.fit(X)
    X=scaler.transform(X)
    
    mean_fpr = np.linspace(0, 1, 250)
    aucs = np.zeros((repeat,5))
    acc = np.zeros((repeat,5))
    f1 = np.zeros((repeat,5))
    importance = np.zeros((repeat,5,numFeature))
    TPRS = []
    AUCS = []
    fname = 'filtered'+str(features)+'_'+classes+'_'+clf+'_'+str(estimators)
    for i in range(repeat):
        j = 0
        tprs = []
        aucs = []
        model = classifier(clf, estimators)
        cv = StratifiedKFold(n_splits=5,random_state = 42, shuffle = True)
        
        for train, test in cv.split(X, y):
            probas_ = model.fit(X[train], y[train]).predict_proba(X[test])
            acc[i,j] = model.score(X[test],y[test])
            y_pred = model.predict(X[test])
            f1[i,j]= f1_score(y[test], y_pred, average='weighted')
            importance[i,j,:] =  model.feature_importances_
            
            
            # Compute ROC curve and area under the curve
            fpr, tpr, thresholds = roc_curve(y[test], probas_[:, 1],drop_intermediate='False')
            tprs.append(np.interp(mean_fpr, fpr, tpr))
            tprs[-1][0] = 0.0
           
            aucs.append(auc(fpr, tpr))
            
            j += 1
           
        TPRS.append(tprs)
        AUCS.append(aucs)
    
    TPRS = np.array(TPRS).mean(0) #averaged across the repeated experiments
    AUCS = np.array(AUCS).mean(0) #averaged across the repeated experiments 
    
    importance = importance.mean(0).mean(0)# Averaged across repeated experiments and folds  
    acc = acc.mean(1).mean(0) # Averaged across  folds and then over repeated experiments 
    f1 = f1.mean(1).mean(0) # Averaged across  folds and then over repeated experiments
    
    #Plot SHAP and ROC
    plot_SHAP(model,X,cols,fname,plots_path)
    plot_ROC(TPRS,AUCS,fname,plots_path)
    save_results(acc, f1, importance, cols, fname, results_path)
    
    return acc, f1, TPRS, AUCS, importance
    
                   
            
if  __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument('--features', type=int, help='Number of features to select', default=200)
    parser.add_argument('--classifier', type=str, help='ML classifier to use. Options:[RandomForest, GradientBoosting] ', default='RandomForest')
    parser.add_argument('--estimators', type=int, help='number of estimators for classfiers', default=100)
    parser.add_argument('--repeat', type=int, help='number of experiments run', default=10)
    parser.add_argument('--classes', type=str, help='Binary classes to perform classification for. Options:[CN_MCI, CN_AD, MCI_AD]', default='CN_AD')
    parser.add_argument('--tuning', type=str, help='To perform hyperparameter sweep or not. Options:[sweep, no_sweep]', default='no_sweep')    
    args = parser.parse_args()
    
    if args.tuning == 'no_sweep':
        acc, f1, tprs, aucs, importance = train_ADNI(features = args.features,
                clf = args.classifier,
                estimators = args.estimators,
                classes = args.classes,
                repeat = args.repeat,
                data_path = cfg.data,
                results_path = cfg.results,
                plots_path = cfg.plots         
               )
    
    if args.tuning == 'sweep':
        params = list(itertools.product(*HyperParameters.params))
        for hp in params:
            print("For parameters:",hp)
            acc, f1, tprs, aucs, importance = train_ADNI(features = hp[0],
                clf = hp[1],
                estimators = hp[2],
                classes = hp[3],
                repeat = cfg.repeat,
                data_path = cfg.data,
                results_path = cfg.results,
                plots_path = cfg.plots         
               )
            print(acc, f1, tprs, aucs, importance)


    
 
