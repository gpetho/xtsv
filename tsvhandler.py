#!/usr/bin/python3
# -*- coding: utf-8, vim: expandtab:ts=4 -*-

import logging
logger = logging.getLogger('xtsv')


class HeaderError(ValueError):
    pass


def process_header(fields, source_fields, target_fields):
    if not source_fields.issubset(set(fields)):
        raise HeaderError('Input does not have the required field names ({0}). The following field names found: {1}'.
                          format(sorted(source_fields), fields))
    fields.extend(target_fields)                                    # Add target fields when apply (only for tagging)
    field_names = {name: i for i, name in enumerate(fields)}        # Decode field names
    field_names.update({i: name for i, name in enumerate(fields)})  # Both ways...
    header = '{0}\n'.format('\t'.join(fields))
    return header, field_names


# Only This method is public...
def process(stream, internal_app, conll_comments=False):
    """
    Process the input stream and check the header for the next module in the pipeline (internal_app).
     Five types of internal app is allowed:
     1) "Tokeniser": No source fields, no header, has target fields, free-format text as input, TSV+header output
     2) "Internal module": Has source fields, has header, has target fields, TSV+header input, TSV+header output
     3) "Finalizer": Has source fields, no header, no target fields, TSV+header input, free-format text as output
     4) "Fixed-order TSV importer": No source fields, no header, has target fields, Fixed-order TSV w/o header as input,
      TSV+header output
     5) "Fixed-order TSV processor": No source fields, no header, no target fields, Fixed-order TSV w/o header as input,
      Fixed-order TSV w/o header as output
    :param stream: Line chunked input stream, one token per line (TSV) and emtpy lines as sentence separator,
     or free-format input for tokenisers
    :param internal_app: the initialised xtsv module class as module (type 2 by default)
    :param conll_comments: Allow conll style comments (lines starting with '#') before sentences (default: false)
    :return: Iterator over the processed tokens (iterator of lists of features)
    """
    fixed_order_tsv_input = getattr(internal_app, 'fixed_order_tsv_input', False)
    if len(internal_app.source_fields) > 0 or fixed_order_tsv_input:
        if not fixed_order_tsv_input:
            fields = next(stream).strip().split('\t')  # Read header to fields
        else:
            fields = []
        header, field_names = process_header(fields, internal_app.source_fields, internal_app.target_fields)
        if getattr(internal_app, 'pass_header', True):  # Pass or hold back the header
            yield header

        # Like binding names to indices...
        field_values = internal_app.prepare_fields(field_names)

        logger.info('processing sentences...')
        sen_count = 0
        for sen_count, (sen, comment) in enumerate(sentence_iterator(stream, conll_comments)):
            sen_count += 1
            if len(comment) > 0:
                yield comment

            yield from ('{0}\n'.format('\t'.join(tok)) for tok in internal_app.process_sentence(sen, field_values))
            yield '\n'

            if sen_count % 1000 == 0:
                logger.info('{0}...'.format(sen_count))
        logger.info('{0}...done\n'.format(sen_count))
    else:
        # This is intended to be used by the first module in the pipeline which deals with raw text (eg. tokeniser) only
        yield '{0}\n'.format('\t'.join(internal_app.target_fields))
        yield from internal_app.process_sentence(stream)


def sentence_iterator(input_stream, conll_comments=False):
    curr_sen = []
    curr_comment = ''
    for line in input_stream:
        line = line.strip()
        # Comment handling: Before sentence, line starts with '# ' and comments are allowed by parameter
        # (this allows #tags at the beginning of the sentence commonly used in social mediat)
        if len(curr_sen) == 0 and line.startswith('# ') and conll_comments:
            curr_comment += '{0}\n'.format(line)  # Comment before sentence
        # Blank line handling
        elif len(line) == 0:
            if len(curr_sen) > 0:  # End of sentence
                yield curr_sen, curr_comment
                curr_sen = []
                curr_comment = ''
            else:  # WARNING: Multiple blank line
                logger.warning('Wrong formatted sentences, only one blank line allowed!')
        else:
            curr_sen.append(line.split('\t'))
    if curr_sen:
        logger.warning('No blank line before EOF!')
        yield curr_sen, curr_comment
